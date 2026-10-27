import csv
import json
import sqlite3
from pathlib import Path

import pytest

from products.professional_evidence_customer_surface_compat import _build_vamp_database_v2
from products.vamp_customer_projection import review_window


def packet(root: Path):
    source=root/'SOURCES';source.mkdir(parents=True)
    with (source/'02_evidence_register.csv').open('w') as f:
        w=csv.writer(f);w.writerow(['record_id','customer_supplied_record'])
        w.writerows([['R1','Review period: January-June 2026.'],
                     ['R2','Objective KPA1 requires evidence of two research outputs; one accepted article and one submitted manuscript are present.'],
                     ['R3','KPA3 requires module coordination evidence; the appointment letter and timetable are present.'],
                     ['R4','KPA5 requires community engagement evidence; only an undated planning email is present.']])
    return {'packet_dir':root,'packet_fingerprint':'sha256:actual'}


def test_vamp_preserves_actual_period_objective_count_and_required_quantity(tmp_path: Path):
    p=packet(tmp_path/'packet');db=_build_vamp_database_v2(p,tmp_path/'projection/progress.db')
    with sqlite3.connect(db) as c:
        tasks=c.execute('select title,window_start,window_end,min_required from tasks').fetchall()
        assert len(tasks)==3
        assert all('Review period:' not in t[0] for t in tasks)
        research=next(t for t in tasks if 'research outputs' in t[0])
        assert research[1:]==('2026-01-01','2026-06-30',2)
        assert c.execute('select distinct month_bucket from evidence').fetchall()==[('2026-06',)]
    projection=json.loads((db.parent/'VAMP_DOMAIN_PROJECTION.json').read_text())
    assert projection['review_window']['months']==[f'2026-{i:02d}' for i in range(1,7)]
    assert projection['evidence_dates_independently_verified'] is False


def test_missing_or_conflicting_period_is_never_replaced_with_august_2026():
    with pytest.raises(ValueError,match='review period'):
        review_window([{'customer_supplied_record':'The CV lists 11 outputs.'}])
    with pytest.raises(ValueError,match='conflicting'):
        review_window([{'customer_supplied_record':'Review period: January-June 2026.'},
                       {'customer_supplied_record':'Review period: July-December 2026.'}])


def test_combined_scope_and_objective_source_keeps_objective(tmp_path: Path):
    p={'packet_fingerprint':'sha256:actual'}
    rows=[{'record_id':'ONE','customer_supplied_record':'Review period: January-June 2026.\nObjective KPA1 requires two research outputs.'}]
    db=_build_vamp_database_v2(p,tmp_path/'projection/progress.db',source_rows=rows)
    with sqlite3.connect(db) as c:
        assert c.execute('select count(*) from tasks').fetchone()[0]==1
        assert c.execute('select min_required from tasks').fetchone()[0]==2


def test_period_metadata_alone_cannot_make_an_empty_successful_snapshot(tmp_path: Path):
    with pytest.raises(ValueError,match='objectives'):
        _build_vamp_database_v2({'packet_fingerprint':'actual'},tmp_path/'projection/progress.db',source_rows=[{'customer_supplied_record':'Review period: January-June 2026.'}])


def test_semicolon_scope_and_objective_cannot_make_zero_objectives(tmp_path: Path):
    rows=[{'record_id':'ONE','customer_supplied_record':'Review period: January-June 2026; Objective KPA1 requires two research outputs.'}]
    db=_build_vamp_database_v2({'packet_fingerprint':'actual'},tmp_path/'projection/progress.db',source_rows=rows)
    with sqlite3.connect(db) as c:
        assert c.execute('select count(*) from tasks').fetchone()[0]==1
        assert c.execute('select min_required from tasks').fetchone()[0]==2


def test_customer_objective_statement_cannot_certify_its_own_evidence(tmp_path: Path):
    rows = [
        {'record_id': 'SCOPE', 'customer_supplied_record': 'Review period: January-June 2026.'},
        {'record_id': 'REQUIREMENT', 'customer_supplied_record': 'Objective KPA1 requires two peer-reviewed articles.'},
    ]
    db = _build_vamp_database_v2(
        {'packet_fingerprint': 'sha256:declaration-only'},
        tmp_path / 'projection/progress.db',
        source_rows=rows,
    )
    with sqlite3.connect(db) as con:
        assert con.execute('select count(*) from tasks').fetchone()[0] == 1
        assert con.execute('select count(*) from evidence').fetchone()[0] == 1
        assert con.execute('select count(*) from evidence_task').fetchone()[0] == 0
    projection = json.loads((db.parent / 'VAMP_DOMAIN_PROJECTION.json').read_text())
    assert projection['rows'][0]['task_id'] is not None
    assert projection['rows'][0]['evidence_id'] is not None


def test_zero_quantity_is_not_silently_promoted_to_one_required_output(tmp_path: Path):
    rows = [
        {'record_id': 'SCOPE', 'customer_supplied_record': 'Review period: January-June 2026.'},
        {'record_id': 'OBJECTIVE', 'customer_supplied_record': 'Objective KPA1 requires 0 publications.'},
    ]
    with pytest.raises(ValueError, match='zero|positive|quantity'):
        _build_vamp_database_v2(
            {'packet_fingerprint': 'sha256:zero-source'},
            tmp_path / 'projection/progress.db',
            source_rows=rows,
        )


@pytest.mark.parametrize('statement', [
    'Objective KPA1 requires -2 publications.',
    'Objective KPA1 does not require two publications.',
])
def test_negated_or_negative_quantity_never_becomes_one_required_output(tmp_path: Path, statement: str):
    rows = [
        {'record_id': 'SCOPE', 'customer_supplied_record': 'Review period: January-June 2026.'},
        {'record_id': 'OBJECTIVE', 'customer_supplied_record': statement},
    ]
    with pytest.raises(ValueError, match='negative|negated|quantity'):
        _build_vamp_database_v2(
            {'packet_fingerprint': 'sha256:invalid-quantity'},
            tmp_path / 'projection/progress.db',
            source_rows=rows,
        )


def test_grouped_requirement_quantity_retains_the_full_number(tmp_path: Path):
    rows = [
        {'record_id': 'SCOPE', 'customer_supplied_record': 'Review period: January-June 2026.'},
        {'record_id': 'OBJECTIVE', 'customer_supplied_record': 'Objective KPA1 requires 1,500 indexed records.'},
    ]
    db = _build_vamp_database_v2(
        {'packet_fingerprint': 'sha256:grouped-requirement'},
        tmp_path / 'projection/progress.db',
        source_rows=rows,
    )
    with sqlite3.connect(db) as con:
        assert con.execute('select min_required from tasks').fetchone()[0] == 1500


def test_malformed_grouped_requirement_is_not_truncated_to_a_smaller_target(tmp_path: Path):
    rows = [
        {'record_id': 'SCOPE', 'customer_supplied_record': 'Review period: January-June 2026.'},
        {'record_id': 'OBJECTIVE', 'customer_supplied_record': 'Objective KPA1 requires 1,50 indexed records.'},
    ]
    with pytest.raises(ValueError, match='grouping|quantity|invalid'):
        _build_vamp_database_v2(
            {'packet_fingerprint': 'sha256:malformed-grouping'},
            tmp_path / 'projection/progress.db',
            source_rows=rows,
        )
