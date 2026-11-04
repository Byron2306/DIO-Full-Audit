#!/usr/bin/env python3
"""Consolidate historical execution evidence and current product qualification.

This reads existing runs; it neither executes products nor grants acceptance.
The HTML contains summary information and local artifact links, never source
excerpts or private signing records. Detailed historical findings stay in JSON.
"""
from __future__ import annotations

import hashlib
import html
import csv
import json
import os
import re
import sys
import zipfile
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import quote

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from products.customer_product_router import customer_product_catalog

OUTPUT = ROOT / 'acceptance_runs/68-product-sellability-20261027'
BASELINE = ROOT / 'acceptance_runs/68-product-integration-20261027/68_PRODUCT_EXECUTION_QUALITY_AUDIT.json'
AUDIT = ROOT / 'docs/audits/2026-10-27-sellable-product-pathways.md'
RUN_RECEIPT = 'PROFESSIONAL_EVIDENCE_53_X3_RECEIPT.json'
VAMP_ATTACHMENT_DEMOS = {
    'CPDProof': OUTPUT / 'CPDPROOF_ATTACHMENT_BINDING_DEMO_20261101',
    'PromotionProof': OUTPUT / 'PROMOTIONPROOF_ATTACHMENT_BINDING_DEMO_20261101',
}
ARTICLE_PUBLICATION_STUDIO_EDITORIAL_DEMO = OUTPUT / 'ARTICLE_PUBLICATION_STUDIO_EDITORIAL_REVIEW_20261104_V2'
CORRESPONDENCE_REVIEW_VALIDATION_DEMO = OUTPUT / 'CORRESPONDENCE_EDITOR_REVIEW_VALIDATION_20261102_V4'

# Aliases share one service capability and the same explicitly identified
# evidence. A Studio name does not create another independent acceptance.
CAPABILITIES = {
    'report_and_pitch': {
        'offers': ['Report & Pitch Studio'],
        'root': 'report-pitch/reviewed-final-v4',
        'service': 'Source-based decision brief and editable presentation',
        'limit': 'Interpretation, recommendations and presentation fit require review; the deck is a restrained evidence briefing.',
    },
    'article_preparation': {
        'offers': ['Article Publication', 'Article Publication Studio'],
        'root': 'report-pitch/reviewed-final-v4',
        'service': 'Attributed article preparation from supplied sources',
        'limit': 'Editorial quality, usage rights and citation authenticity require review; journal acceptance is unproved.',
    },
    'professional_correspondence': {
        'offers': ['Professional Correspondence', 'Professional Correspondence Studio'],
        'root': 'customer-pathways-delivery-v8/correspondence',
        'service': 'Factual records-request or reconciliation letter',
        'limit': 'The sender reviews facts, tone, position and commitments; sending authority is separate.',
    },
    'contract_review_preparation': {
        'offers': ['Contract Desk'],
        'root': 'customer-pathways-delivery-v8/contract',
        'service': 'Clause and obligation register with reviewer questions',
        'limit': 'The contract owner or legal reviewer confirms meaning, triggers and deadlines; enforceability is not determined.',
    },
    'finance_readiness_preparation': {
        'offers': ['Finance Readiness', 'Finance Readiness Studio'],
        'root': 'customer-pathways-delivery-v8/readiness',
        'service': 'Document gap pack and transparent financial calculations',
        'limit': 'An accountant or lender checks requirements, source records and conclusions; no lending or valuation decision is made.',
    },
    'funding_research': {
        'offers': ['FundingFinder'],
        'root': 'funding-finder/reviewed',
        'service': 'Dated opportunity shortlist and application-readiness questions',
        'limit': 'Confirm live availability and full rules with the funder; synthetic applicant examples do not certify eligibility.',
    },
    'launch_kit_preparation': {
        'offers': ['Launch Studio'],
        'root': 'launch-reviewed_v2',
        'service': 'Source-bound channel assets and owned-brand launch kit',
        'limit': 'Brand, claims, rights, destination and release owners require review; no advertising spend or publication is authorized by qualification.',
    },
    'evidence_reconciliation_preparation': {
        'offers': ['Evidex EvidenceOps'],
        'root': 'customer-pathways-delivery-v8/evidex',
        'service': 'Claim-to-record organization and reconciliation preparation',
        'limit': 'Obtain underlying dated records and establish population/period comparability; reported quantities are not verified delivery.',
    },
    'performance_coverage_preparation': {
        'offers': ['VAMP Performance'],
        'root': 'vamp-quality/customer-release-candidate',
        'service': 'Performance evidence coverage preparation',
        'limit': 'Confirm scope, objective mapping and underlying outputs; event dates and achievement sufficiency are unverified. No employee rating or promotion/CPD decision.',
    },
}

RUN_GROUPS = {
    'sophia_held_diagnostic': 'sophia-recovery/journeys-bounded-repair',
    'afrikaans_packaging': 'lingua-afrikaans/canonical-profiled',
    'vamp_evidex': 'vamp-evidex-final',
}
FULL_PORTFOLIO_REPORT = OUTPUT / 'DIO_68_FULL_PIPELINE_EXECUTION_EVIDENCE_20261102.json'
HOMS_ASSESS_QUALITY_REPORT = OUTPUT / 'HOMS_ASSESS_FEEDBACK_UNIT_CONSISTENCY_GATE_20261102.json'
NATIVE_EXTENSION_BATCH = OUTPUT / 'canon-extension-native-current-chain-20261101/isolated-root/state/product_grade/canon_extensions/NATIVE_CANON_EXTENSION_PRODUCT_GRADE_BATCH_RECEIPT.json'
NATIVE_EXTENSION_MATERIALIZATION = OUTPUT / 'canon-extension-native-current-chain-20261101/isolated-root/CURRENT_PROFILE_MATERIALIZATION_BATCH_RECEIPT.json'
HOMS_GRADE_EXAM_AUDIT = OUTPUT / 'HOMS_RANDOM_GRADE_EXAM_SET_CONTENT_AUDIT_20261102.json'
HOMS_GRADE12_CAPS_MAPPING_EVIDENCE = OUTPUT / 'HOMS_GRADE12_BUSINESS_CAPS_MAPPING_CORRECTION_20261101.json'
HOMS_GRADE_EXAM_PDF_MANIFEST = ROOT / 'deliverables/homs_random_grade_exam_set_20261101/PRINT_READY_PDF_MANIFEST.json'
FUNDING_FINDER_LIVE_REFRESH = OUTPUT / 'FUNDINGFINDER_LIVE_REFRESH_RECEIPT_20261104_V3.json'
FUNDING_FINDER_LIVE_CUSTOMER_ROUTE = OUTPUT / 'FUNDINGFINDER_LIVE_CUSTOMER_ROUTE_20261104_V3'
FUNDING_FINDER_LIVE_CUSTOMER_PACKET = OUTPUT / 'FUNDINGFINDER_LIVE_CUSTOMER_ROUTE_PACKET_20261104_V3.json'
FUNDING_FINDER_SERVICESETA_ROUTE = OUTPUT / 'FUNDINGFINDER_SERVICESETA_CUSTOMER_ROUTE_20261104_V11'
FUNDING_FINDER_SERVICESETA_PACKET = OUTPUT / 'FUNDINGFINDER_SERVICESETA_CUSTOMER_PACKET_20261104_V11.json'
FUNDING_FINDER_SERVICESETA_EVIDENCE = OUTPUT / 'FUNDINGFINDER_SERVICESETA_CUSTOMER_ROUTE_20261104_V11.json'
FUNDING_FINDER_THREE_WINDOW_RUN = OUTPUT / 'FUNDINGFINDER_SERVICESETA_THREE_WINDOW_REVIEW_20261104_V4'
FUNDING_FINDER_THREE_WINDOW_DATA = FUNDING_FINDER_THREE_WINDOW_RUN / 'THREE_WINDOW_REVIEW.json'
FUNDING_FINDER_THREE_WINDOW_RECEIPT = FUNDING_FINDER_THREE_WINDOW_RUN / 'THREE_WINDOW_REVIEW_RECEIPT.json'
MARKET_RADAR_CURRENT_ROUTE = OUTPUT / 'MARKET_RADAR_CUSTOMER_EXECUTION_20261104_V3'
MARKET_RADAR_CURRENT_EVIDENCE = OUTPUT / 'MARKET_RADAR_CUSTOMER_EXECUTION_20261104_V3.json'
HOMS_ASSESS_GATE_FOLLOWUP = OUTPUT / 'HOMS_ASSESS_FEEDBACK_UNIT_GATE_FOLLOWUP_20261102.json'
HOMS_ASSESS_SCORE_STABILITY = OUTPUT / 'HOMS_ASSESS_SCORE_STABILITY_EXPERIMENT_20261102.json'
HOMS_ASSESS_SCORE_WITHHOLDING = OUTPUT / 'HOMS_ASSESS_SCORE_WITHHOLDING_EVIDENCE_20261102.json'
HOMS_ASSESS_QUESTION_SCOPED_CONFLICT_REPLAY = OUTPUT / 'HOMS_ASSESS_QUESTION_SCOPED_CONFLICT_REPLAY_20261104_V2/HOMS_ASSESS_QUESTION_SCOPED_CONFLICT_REPLAY.json'
HOMS_ASSESS_REASONING_REPEATABILITY = OUTPUT / 'HOMS_ASSESS_REASONING_AND_REPEATABILITY_EVIDENCE_20261102.json'
HOMS_ASSESS_CLEAN_RUN_REPEATABILITY = OUTPUT / 'HOMS_ASSESS_CLEAN_RUN_AND_REPEATABILITY_EVIDENCE_20261102.json'
HOMS_ASSESS_QUOTE_SUGGESTIONS = OUTPUT / 'HOMS_ASSESS_POINTWISE_QUOTE_SUGGESTIONS_20261102_V5_REVIEW_CONTEXT_BOUND.json'
HOMS_ASSESS_RUN_CONTEXT = OUTPUT / 'HOMS_ASSESS_RUN_CONTEXT_20261102_V1'
HOMS_ASSESS_MODEL_COMPARISON = OUTPUT / 'HOMS_ASSESS_MODEL_COMPARISON_QWEN3_4B_20261101.json'
HOMS_ASSESS_QWEN3_NOTHINK_RUN = OUTPUT / 'HOMS_ASSESS_CUSTOMER_PACKET_EXECUTION_20261102_G10_V35_QWEN3_NOTHINK'
HOMS_ASSESS_POINTWISE_COMPLETENESS = OUTPUT / 'HOMS_ASSESS_CUSTOMER_PACKET_EXECUTION_20261103_G10_V23/POINTWISE_COMPLETENESS_EXECUTION_EVIDENCE.json'
HOMS_ASSESS_POINT_QUOTE_GROUNDING = OUTPUT / 'HOMS_ASSESS_POINT_QUOTE_GROUNDING_AUDIT_20261102.json'
HOMS_ASSESS_POINT_QUOTE_REPAIR = OUTPUT / 'HOMS_ASSESS_POINT_QUOTE_REPAIR_20261102_V1/POINT_QUOTE_BOUNDED_REPAIR_EVIDENCE.json'
HOMS_ASSESS_POINT_QUOTE_REPAIR_ATTEMPTS = [
    OUTPUT / 'HOMS_ASSESS_POINT_QUOTE_REPAIR_20261102_V2_QWEN3_4B/ATTEMPT_STATUS.json',
    OUTPUT / 'HOMS_ASSESS_POINT_QUOTE_REPAIR_20261102_V3_GRANITE33/ATTEMPT_STATUS.json',
]
HOMS_ASSESS_POINT_QUOTE_REVIEW_SURFACE = OUTPUT / 'HOMS_ASSESS_POINTWISE_REVIEW_POINT_QUOTE_SURFACE_20261102_V1'
HOMS_ASSESS_SINGLE_QUESTION_QUOTE_PROBE = OUTPUT / 'HOMS_ASSESS_SINGLE_QUESTION_POINT_QUOTE_PROBE_20261102_V5/PROBE_EVIDENCE.json'
HOMS_ASSESS_GROUNDING_COMPARISON_PROBES = [
    OUTPUT / 'HOMS_ASSESS_SINGLE_QUESTION_QUOTE_PROBE_20261102_V1.json',
    OUTPUT / 'HOMS_ASSESS_SINGLE_QUESTION_QUOTE_PROBE_20261102_QWEN3_V1.json',
]
HOMS_ASSESS_QUESTION_SCOPED_POINTWISE = OUTPUT / 'HOMS_ASSESS_QUESTION_SCOPED_20261102_V8B/QUESTION_SCOPED_POINTWISE_EVIDENCE.json'
HOMS_ASSESS_SMALL_CHUNK_POINTWISE = OUTPUT / 'HOMS_ASSESS_SCOPED_REPAIR_PROMPT_20261102_V11/SCOPED_REPAIR_PROMPT_EVIDENCE.json'
HOMS_ASSESS_SINGLE_POINT_REPAIR = OUTPUT / 'HOMS_ASSESS_SINGLE_POINT_REPAIR_20261102_V12/SINGLE_POINT_REPAIR_COMPARISON.json'
HOMS_ASSESS_STRICT_POINTWISE_SCHEMA = OUTPUT / 'HOMS_ASSESS_STRICT_SCORING_SCHEMA_20261102_V13/STRICT_POINTWISE_SCHEMA_EXECUTION_EVIDENCE.json'
HOMS_ASSESS_POSITIVE_QUOTE_SCHEMA = OUTPUT / 'HOMS_ASSESS_GROUNDED_QUOTE_SCHEMA_20261102_V14/POSITIVE_QUOTE_SCHEMA_EXECUTION_EVIDENCE.json'
HOMS_ASSESS_UNGROUNDED_REVIEW_CONTEXT = OUTPUT / 'HOMS_ASSESS_UNGROUNDED_REVIEW_CONTEXT_20261102_V16/HOMS_ASSESS_UNGROUNDED_REVIEW_CONTEXT_EVIDENCE.json'
HOMS_ASSESS_UNBOUND_QUOTE_DIAGNOSTICS = OUTPUT / 'HOMS_ASSESS_UNBOUND_QUOTE_DIAGNOSTICS_20261102_V19/HOMS_ASSESS_UNBOUND_QUOTE_DIAGNOSTICS_EVIDENCE.json'
HOMS_ASSESS_QWEN_SINGLE_QUESTION_PROBE = OUTPUT / 'HOMS_ASSESS_QWEN3_G10_Q13_PROBE_20261102_V15/PROBE_EVIDENCE.json'
HOMS_ASSESS_REVIEW_COPY_CLARITY = OUTPUT / 'HOMS_ASSESS_REVIEW_COPY_CLARITY_EXECUTION_20261103.json'
HOMS_ASSESS_QUESTION_SCOPED_REPAIR = OUTPUT / 'HOMS_ASSESS_QUESTION_SCOPED_POINT_REPAIR_EXECUTION_20261103.json'
HOMS_ASSESS_STRUCTURED_POINTWISE = OUTPUT / 'HOMS_ASSESS_STRUCTURED_POINTWISE_EXECUTION_20261103.json'
HOMS_ASSESS_TAIL_RECOVERY = OUTPUT / 'HOMS_ASSESS_TAIL_RECOVERY_20261102_V1'
HOMS_ASSESS_ADJUDICATION_HANDOFF = OUTPUT / 'HOMS_ASSESS_CUSTOMER_PACKET_EXECUTION_20261103_G10_V26/EDUCATOR_HANDOFF_V1/EDUCATOR_ADJUDICATION_HANDOFF_EXECUTION_RECEIPT.json'
HOMS_ASSESS_RECONCILIATION_DEMO = OUTPUT / 'HOMS_ASSESS_EDUCATOR_RECONCILIATION_DEMO_20261102_V8/EDUCATOR_MARK_RECONCILIATION_EVIDENCE.json'
HOMS_ASSESS_REVIEW_SOURCE_BLOCK_REFRESH = OUTPUT / 'HOMS_ASSESS_REVIEW_SOURCE_ANSWER_BLOCKS_20261101_V1'
HOMS_ASSESS_COMPLETE_ANSWER_SURFACE = OUTPUT / 'HOMS_ASSESS_DEFINITION_CONFLICT_PROBE_20261102/EXECUTION_V3'
HOMS_ASSESS_DISTANCE_CONFLICT_SURFACE = OUTPUT / 'HOMS_ASSESS_DEFINITION_CONFLICT_PROBE_20261102/EXECUTION_V4'
EVIDEX_SCOPE_COMPARABILITY_DEMO = OUTPUT / 'EVIDEX_SCOPE_COMPARABILITY_DEMO_20261104_V6'
EVIDEX_ATTACHED_SOURCE_DEMO = OUTPUT / 'EVIDEX_ATTACHED_SOURCE_DEMO_20261102_V1'
HOMS_ASSESS_POINTWISE_RECOVERY_COMPARISON = OUTPUT / 'HOMS_ASSESS_POINTWISE_PROMPT_RECOVERY_COMPARISON_20261103.json'
HOMS_CURRICULUM_CAPS_EVIDENCE = OUTPUT / 'HOMS_CURRICULUM_CAPS_SOURCE_BOUND_EVIDENCE_20261101.json'
HOMS_CURRICULUM_TRACEABILITY_EVIDENCE = OUTPUT / 'HOMS_CURRICULUM_TRACEABILITY_EVIDENCE_20261101.json'
HOMS_CURRICULUM_CUSTOMER_EXECUTION = OUTPUT / 'HOMS_CURRICULUM_CUSTOMER_PACKET_EXECUTION_20261105_V3'
HOMS_CURRICULUM_RANDOMIZED_SPINE_BATCH = OUTPUT / 'HOMS_CURRICULUM_RANDOMIZED_SPINE_CUSTOMER_GRADE_BATCH_20261104_V27'
HOMS_CURRICULUM_RANDOMIZED_SPINE_INPUT_BATCH = OUTPUT / 'HOMS_CURRICULUM_RANDOMIZED_SPINE_SYNTHETIC_GRADE_BATCH_20261104_V27'
HOMS_CURRICULUM_MASTER_INDEX = HOMS_CURRICULUM_RANDOMIZED_SPINE_BATCH / 'index.html'
HOMS_CURRICULUM_MASTER_INDEX_MANIFEST = HOMS_CURRICULUM_RANDOMIZED_SPINE_BATCH / 'HOMS_CURRICULUM_MASTER_INDEX_MANIFEST.json'
HOMS_EXAM_LEARNING_EVIDENCE = OUTPUT / 'HOMS_EXAM_LEARNING_INTEGRATION_EVIDENCE_20261101.json'
HOMS_MODERATION_BATCH = ROOT / 'deliverables/homs_random_grade_exam_set_20261101/moderation_scope_revision_20261104_v15/HOMS_MODERATION_BATCH_RECEIPT.json'
HOMS_MODERATE_COHORT_DEMO = OUTPUT / 'HOMS_MODERATE_COHORT_ANALYSIS_SYNTHETIC_20261102_V3'
HOMS_GRADE_EXAM_INDEX = ROOT / 'deliverables/homs_random_grade_exam_set_20261101/index.html'
LAUNCH_STUDIO_RENDERED_SOURCE_BINDING = OUTPUT / 'LAUNCH_STUDIO_RENDERED_SOURCE_BINDING_20261101_V1'
LAUNCH_STUDIO_VISUAL_REVIEW = ROOT / 'acceptance_runs/68-product-sellability-20261027/launch-reviewed_v2/LAUNCH_CREATIVE_VISUAL_REVIEW.json'
LAUNCH_STUDIO_CUSTOMER_REVIEW_BUNDLE = OUTPUT / 'LAUNCH_STUDIO_CUSTOMER_REVIEW_BUNDLE_20261104_V2'
POPIA_PROCESSING_ACTIVITY_RUN = OUTPUT / 'POPIA_READINESS_PROCESSING_ACTIVITY_20261101_V2'
CORPORATE_READINESS_ACTION_RUN = OUTPUT / 'CORPORATE_READINESS_ACTION_REGISTER_20261101_V1'
CORPORATE_READINESS_ACTION_ASSIGNMENT_DEMO = OUTPUT / 'CORPORATE_READINESS_CUSTOMER_TARGET_ASSIGNMENT_DEMO_20261101'
ENTREPRENEURPROOF_SOURCE_ISSUE_RUN = OUTPUT / 'ENTREPRENEURPROOF_SOURCE_ISSUE_LINEAGE_20261104_V2'
READINESS_SOURCE_ISSUE_RUNS = {
    'Corporate Readiness': OUTPUT / 'CORPORATE_READINESS_SOURCE_ISSUE_LINEAGE_20261104_V2',
    'Finance Readiness': OUTPUT / 'FINANCE_READINESS_SOURCE_ISSUE_LINEAGE_20261104_V2',
    'Finance Readiness Studio': OUTPUT / 'FINANCE_READINESS_STUDIO_SOURCE_ISSUE_LINEAGE_20261104_V2',
    'POPIA Readiness': OUTPUT / 'POPIA_READINESS_SOURCE_ISSUE_LINEAGE_20261104_V2',
    'InvestorProof': OUTPUT / 'INVESTORPROOF_SOURCE_ISSUE_LINEAGE_20261104_V2',
}
READINESS_SOURCE_ISSUE_SUPERSEDED_RUNS = {
    'Corporate Readiness': OUTPUT / 'CORPORATE_READINESS_SOURCE_ISSUE_LINEAGE_20261101_V1',
    'Finance Readiness': OUTPUT / 'FINANCE_READINESS_SOURCE_ISSUE_LINEAGE_20261101_V1',
    'Finance Readiness Studio': OUTPUT / 'FINANCE_READINESS_STUDIO_SOURCE_ISSUE_LINEAGE_20261101_V1',
    'POPIA Readiness': OUTPUT / 'POPIA_READINESS_SOURCE_ISSUE_LINEAGE_20261101_V1',
    'InvestorProof': OUTPUT / 'INVESTORPROOF_SOURCE_ISSUE_LINEAGE_20261101_V1',
    'EntrepreneurProof': OUTPUT / 'ENTREPRENEURPROOF_SOURCE_ISSUE_LINEAGE_20261101_V1',
}
READINESS_ISSUE_REVIEW_SURFACES = {
    'Corporate Readiness': OUTPUT / 'CORPORATE_READINESS_SOURCE_ISSUE_LINEAGE_20261104_V2',
    'Finance Readiness': OUTPUT / 'FINANCE_READINESS_SOURCE_ISSUE_LINEAGE_20261104_V2',
    'Finance Readiness Studio': OUTPUT / 'FINANCE_READINESS_STUDIO_SOURCE_ISSUE_LINEAGE_20261104_V2',
    'POPIA Readiness': OUTPUT / 'POPIA_READINESS_SOURCE_ISSUE_LINEAGE_20261104_V2',
    'InvestorProof': OUTPUT / 'INVESTORPROOF_SOURCE_ISSUE_LINEAGE_20261104_V2',
    'EntrepreneurProof': OUTPUT / 'ENTREPRENEURPROOF_SOURCE_ISSUE_LINEAGE_20261104_V2',
}
EIGHT_SPECIALIST_QUALIFICATION_RUN = OUTPUT / 'EIGHT_SPECIALIST_CUSTOMER_QUALIFICATION_20261102_V2'
EIGHT_SPECIALIST_QUALIFICATION_PRODUCTS = {
    'AuditProof', 'QualityProof', 'VendorProof', 'AssuranceRoom',
    'DiligenceRoom', 'DonorProof', 'ImpactProof', 'ProgrammeProof',
}
SITE_STUDIO_ACCESSIBILITY_RUN = OUTPUT / 'SITE_STUDIO_ACCESSIBILITY_ROUTE_20261102_V1'
SITE_STUDIO_PROFESSIONAL_DRAFT_RUN = OUTPUT / 'SITE_STUDIO_PROFESSIONAL_DRAFT_20261104_V3'
OFFER_LAB_SOURCE_REVIEW_RUN = OUTPUT / 'OFFER_LAB_SOURCE_REVIEW_ROUTE_20261104_V5'
VESPER_DESK_SOURCE_REVIEW_RUN = OUTPUT / 'VESPER_DESK_SOURCE_REVIEW_ROUTE_20261102_V3'
EVIDENCE_SOURCE_ISSUE_RUNS = {
    'AI IncidentRoom': OUTPUT / 'AI_INCIDENTROOM_SOURCE_ISSUE_LINEAGE_20261101_V1',
    'AssuranceRoom': OUTPUT / 'ASSURANCEROOM_SOURCE_ISSUE_LINEAGE_20261101_V1',
    'AuditProof': OUTPUT / 'AUDITPROOF_SOURCE_ISSUE_LINEAGE_20261101_V1',
    'CertificationProof': OUTPUT / 'CERTIFICATIONPROOF_SOURCE_ISSUE_LINEAGE_20261101_V1',
    'ControlDrift': OUTPUT / 'CONTROLDRIFT_SOURCE_ISSUE_LINEAGE_20261101_V1',
    'CriticalAI Assurance': OUTPUT / 'CRITICALAI_ASSURANCE_SOURCE_ISSUE_LINEAGE_20261101_V1',
    'CyberAssurance': OUTPUT / 'CYBERASSURANCE_SOURCE_ISSUE_LINEAGE_20261101_V1',
    'DiligenceRoom': OUTPUT / 'DILIGENCEROOM_SOURCE_ISSUE_LINEAGE_20261101_V1',
    'DonorProof': OUTPUT / 'DONORPROOF_SOURCE_ISSUE_LINEAGE_20261101_V1',
    'DORA Vendor Assurance': OUTPUT / 'DORA_VENDOR_ASSURANCE_SOURCE_ISSUE_LINEAGE_20261101_V1',
    'ImpactProof': OUTPUT / 'IMPACTPROOF_SOURCE_ISSUE_LINEAGE_20261101_V1',
    'IncidentProof': OUTPUT / 'INCIDENTPROOF_SOURCE_ISSUE_LINEAGE_20261101_V1',
    'ModelProof': OUTPUT / 'MODELPROOF_SOURCE_ISSUE_LINEAGE_20261101_V1',
    'ProgrammeProof': OUTPUT / 'PROGRAMMEPROOF_SOURCE_ISSUE_LINEAGE_20261101_V1',
    'ProjectProof': OUTPUT / 'PROJECTPROOF_SOURCE_ISSUE_LINEAGE_20261101_V1',
    'QualityProof': OUTPUT / 'QUALITYPROOF_SOURCE_ISSUE_LINEAGE_20261101_V1',
    'ReleaseProof': OUTPUT / 'RELEASEPROOF_SOURCE_ISSUE_LINEAGE_20261101_V1',
    'SupplierCyberProof': OUTPUT / 'SUPPLIERCYBERPROOF_SOURCE_ISSUE_LINEAGE_20261101_V1',
    'VendorProof': OUTPUT / 'VENDORPROOF_SOURCE_ISSUE_LINEAGE_20261101_V1',
}
AI_INCIDENTROOM_TIMELINE_RUN = OUTPUT / 'AI_INCIDENTROOM_LITERAL_TIMELINE_20261102_V1'
INCIDENTPROOF_TIMELINE_RUN = OUTPUT / 'INCIDENTPROOF_LITERAL_TIMELINE_20261102_V1'
MODELPROOF_SPECIALIST_REVIEW_RUN = OUTPUT / 'MODELPROOF_SPECIALIST_REVIEW_20261102_V1'
QUALITYPROOF_CAPA_TRACKER_RUN = OUTPUT / 'QUALITYPROOF_CAPA_TRACKER_20261102_V1'
VENDORPROOF_DOCUMENT_REQUEST_RUN = OUTPUT / 'VENDORPROOF_DOCUMENT_REQUESTS_20261102_V1'
AUDITPROOF_EXCEPTION_TRACKER_RUN = OUTPUT / 'AUDITPROOF_ACCESS_REVIEW_TRACKER_20261102_V1'
DONORPROOF_EXPENDITURE_TRACKER_RUN = OUTPUT / 'DONORPROOF_EXPENDITURE_TRACKER_20261102_V1'
IMPACTPROOF_FOLLOWUP_REQUEST_RUN = OUTPUT / 'IMPACTPROOF_FOLLOWUP_REQUEST_20261102_V1'
OBLIGATION_FAMILY_SOURCE_REVIEWS = {
    'GrantProof': ('grantproof', OUTPUT / 'GRANTPROOF_SOURCE_ALIGNED_REVIEW_20261104_V5'),
    'PermitProof': ('permitproof', OUTPUT / 'PERMITPROOF_SOURCE_ALIGNED_REVIEW_20261104_V1'),
    'PolicyProof': ('policyproof', OUTPUT / 'POLICYPROOF_SOURCE_ALIGNED_REVIEW_20261104_V1'),
    'TenderProof': ('tenderproof', OUTPUT / 'TENDERPROOF_SOURCE_ALIGNED_REVIEW_20261104_V1'),
}
PROGRAMMEPROOF_ATTENDANCE_TRACKER_RUN = OUTPUT / 'PROGRAMMEPROOF_ATTENDANCE_TRACKER_20261102_V1'
HOMS_GRADE_CROSSWALKS = ROOT / 'deliverables/homs_random_grade_exam_set_20261101/learning_crosswalks/HOMS_GRADE_LEARNING_CROSSWALK_BATCH_RECEIPT.json'
HOMS_LEARNING_STUDIO_BATCH = ROOT / 'deliverables/homs_learning_studio_grade_batch_20261104_V31'
HOMS_LEARNING_STUDIO_BATCH_AUDIT = OUTPUT / 'HOMS_LEARNING_STUDIO_GRADE_BATCH_AUDIT_20261104_V31.json'
HOMS_LEARNING_STUDIO_MASTER_INDEX = HOMS_LEARNING_STUDIO_BATCH / 'index.html'
HOMS_LEARNING_STUDIO_MASTER_INDEX_MANIFEST = HOMS_LEARNING_STUDIO_BATCH / 'HOMS_LEARNING_STUDIO_MASTER_INDEX_MANIFEST.json'
HOMS_LEARNING_STUDIO_CUSTOMER_DEMO = OUTPUT / 'HOMS_LEARNING_STUDIO_CUSTOMER_PACKET_EXECUTION_20261102_G01_V1'
HOMS_LEARNING_STUDIO_CUSTOMER_GRADE_BATCH = OUTPUT / 'HOMS_LEARNING_STUDIO_CUSTOMER_GRADE_BATCH_20261104_V30'
HOMS_EXAM_CUSTOMER_DEMO = OUTPUT / 'HOMS_EXAM_CUSTOMER_PACKET_EXECUTION_20261102_G03_V1'
HOMS_EXAM_CUSTOMER_GRADE_BATCH = OUTPUT / 'HOMS_EXAM_CUSTOMER_GRADE_BATCH_20261104_V45'
HOMS_BEST_EXAM_CANDIDATE_SHORTLIST = OUTPUT / 'HOMS_BEST_EXAM_CANDIDATES_SHORTLIST_20261104.json'
HOMS_CURATED_CANDIDATE_BUNDLE = ROOT / 'deliverables/homs_best_randomized_exam_candidates_20261104_v2'
HOMS_GRADE12_ACCURACY_REVISION = OUTPUT / 'HOMS_GRADE12_BUSINESS_STUDIES_ACCURACY_REVISION_20261104.json'
HOMS_SUBJECT_REPRODUCIBILITY_AUDIT = ROOT / 'deliverables/homs_random_grade_exam_set_20261101/RANDOM_SUBJECT_REPRODUCIBILITY_AUDIT_20261102.json'
CPDPROOF_ATTACHMENT_DATE_REVIEW_DEMO = OUTPUT / 'CPDPROOF_ATTACHMENT_DATE_REVIEW_20261102_V2'
CPDPROOF_POINT_RECONCILIATION_DEMO = OUTPUT / 'CPDPROOF_POINT_RECONCILIATION_20261102_V3'
CPDPROOF_PDF_ATTACHMENT_REVIEW = OUTPUT / 'CPDPROOF_PDF_ATTACHMENT_REVIEW_20261102_V2'
PROMOTIONPROOF_ATTACHMENT_RECONCILIATION_DEMO = OUTPUT / 'PROMOTIONPROOF_ATTACHMENT_RECONCILIATION_20261102_V1'
PROMOTIONPROOF_PDF_ATTACHMENT_REVIEW = OUTPUT / 'PROMOTIONPROOF_PDF_ATTACHMENT_REVIEW_20261102_V2'
HOMS_MODERATE_CUSTOMER_DEMO = OUTPUT / 'HOMS_MODERATE_CUSTOMER_PACKET_EXECUTION_20261102_G03_V1'
HOMS_MODERATE_CUSTOMER_GRADE_BATCH = OUTPUT / 'HOMS_MODERATE_CUSTOMER_GRADE_BATCH_20261104_V34'
HOMS_MODERATE_MASTER_INDEX = HOMS_MODERATE_CUSTOMER_GRADE_BATCH / 'index.html'
HOMS_MODERATE_MASTER_INDEX_MANIFEST = HOMS_MODERATE_CUSTOMER_GRADE_BATCH / 'HOMS_MODERATE_MASTER_INDEX_MANIFEST.json'
HOMS_ASSESS_CUSTOMER_DEMO = OUTPUT / 'HOMS_ASSESS_SCORE_FIELD_GATE_EXECUTION_20261101_V1'
HOMS_ASSESS_SOURCE_GROUNDED_DEMO = OUTPUT / 'HOMS_ASSESS_SCORE_FIELD_GATE_EXECUTION_20261101_V1'
HOMS_ASSESS_GRAPH_CONFLICT_EVIDENCE = OUTPUT / 'HOMS_ASSESS_SOURCE_GROUNDED_GRAPH_CONFLICT_20261101_V3.json'
HOMS_ASSESS_FRESH_GUARD_RUN = OUTPUT / 'HOMS_ASSESS_CUSTOMER_PACKET_EXECUTION_20261107_G10_V29'
HOMS_ASSESS_INTERACTIVE_EDUCATOR_RUN = OUTPUT / 'HOMS_ASSESS_CUSTOMER_PACKET_EXECUTION_20261102_G10_V33_INTERACTIVE_EDUCATOR_REVIEW'
HOMS_ASSESS_GROUNDED_ADJUDICATION_RUN = OUTPUT / 'HOMS_ASSESS_CUSTOMER_PACKET_EXECUTION_20261102_G10_V12'
HOMS_ASSESS_PACKET_PATH_REPAIR = OUTPUT / 'HOMS_ASSESS_SOURCE_PACKET_REPAIRED_20261102/PACKET_PATH_REPAIR_EVIDENCE.json'
HOMS_ASSESS_GRANITE33_COMPARISON_RUN = OUTPUT / 'HOMS_ASSESS_CUSTOMER_PACKET_EXECUTION_20261102_G10_V31_GRANITE33_DEFAULT'
HOMS_ASSESS_DEFINITION_CONFLICT_DEMO = OUTPUT / 'HOMS_ASSESS_DEFINITION_CONFLICT_PROBE_20261102/EXECUTION_V2'
HOMS_ASSESS_CONFLICT_HOLD_DEMO = OUTPUT / 'HOMS_ASSESS_SCORE_FIELD_GATE_EXECUTION_20261101_V1'
HOMS_ASSESS_CONFLICT_HOLD_EVIDENCE = OUTPUT / 'HOMS_ASSESS_CUSTOMER_PACKET_EXECUTION_20261103_G10_V29/HOMS_ASSESS_CONFLICT_HOLD_PRESENTATION_20261101_V31.json'
HOMS_QUESTION_CAPS_ALIGNMENT = ROOT / 'deliverables/homs_random_grade_exam_set_20261101/CAPS_QUESTION_ALIGNMENT_ALL_GRADES_20261101.json'
HOMS_CAPS_SOURCE_EXCERPT_REVIEW = ROOT / 'deliverables/homs_random_grade_exam_set_20261101/caps_source_excerpt_reviews_20261104_v28'
HOMS_ACCREDITATION_CUSTOMER_EVIDENCE = OUTPUT / 'HOMS_ACCREDITATION_CUSTOMER_PACKET_EVIDENCE_20261101.json'
HOMS_ACCREDITATION_CUSTOMER_RUN = OUTPUT / 'HOMS_ACCREDITATION_CUSTOMER_PACKET_EXECUTION_20261101_V4'
HOMS_ACCREDITATION_REVIEW_WORKSPACE = HOMS_ACCREDITATION_CUSTOMER_RUN / 'customer_delivery/ACCREDITATION_REVIEW_WORKSPACE.html'
HOMS_ACCREDITATION_REVIEW_WORKSHEET = HOMS_ACCREDITATION_CUSTOMER_RUN / 'customer_delivery/ACCREDITATION_REVIEW_WORKSHEET.csv'
HOMS_ACCREDITATION_REVIEW_MANIFEST = HOMS_ACCREDITATION_CUSTOMER_RUN / 'customer_delivery/ACCREDITATION_REVIEW_WORKSPACE_MANIFEST.json'
DOCUMENT_STUDIO_LOCALIZE_FOLLOWUP = OUTPUT / 'DOCUMENT_STUDIO_LOCALIZE_ADVISORY_TERMINOLOGY_EVIDENCE_20261102.json'
DOCUMENT_STUDIO_LOCALIZE_CUSTOMER_DEMO = OUTPUT / 'DOCUMENT_STUDIO_LOCALIZE_CUSTOMER_EXECUTION_20261103_V6'
DOCUMENT_STUDIO_LOCALIZE_REVIEW_HANDOFF = DOCUMENT_STUDIO_LOCALIZE_CUSTOMER_DEMO / 'LINGUA_HASH_BOUND_REVIEW_HANDOFF.json'
DOCUMENT_STUDIO_LOCALIZE_REVIEW_WORKSPACE = DOCUMENT_STUDIO_LOCALIZE_CUSTOMER_DEMO / 'DOCUMENT_STUDIO_LOCALIZE_AFRIKAANS_REVIEW.html'
DOCUMENT_STUDIO_LOCALIZE_REVIEW_WORKSPACE_RECEIPT = DOCUMENT_STUDIO_LOCALIZE_CUSTOMER_DEMO / 'DOCUMENT_STUDIO_LOCALIZE_AFRIKAANS_REVIEW_RECEIPT.json'
DOCUMENT_STUDIO_LOCALIZE_SEMANTIC_DEMO = OUTPUT / 'DOCUMENT_STUDIO_LOCALIZE_SEMANTIC_TERM_20261101_V4'
DOCUMENT_STUDIO_PUBLISH_CUSTOMER_DEMO = OUTPUT / 'DOCUMENT_STUDIO_PUBLISH_CUSTOMER_EXECUTION_20261104_V4'
ACCESSIBLE_PUBLISH_CUSTOMER_DEMO = OUTPUT / 'ACCESSIBLE_PUBLISH_CUSTOMER_EXECUTION_20261102_V1'
ACCESSIBLE_PUBLISH_SEMANTICS_DEMO = OUTPUT / 'ACCESSIBLE_PUBLISH_CUSTOMER_EXECUTION_20261107_V6'
ACCESSIBLE_PUBLISH_RENDERED_DEMO = OUTPUT / 'ACCESSIBLE_PUBLISH_CUSTOMER_EXECUTION_20261102_V8'
ACCESSIBLE_PUBLISH_LIVE_BROWSER_DEMO = OUTPUT / 'ACCESSIBLE_PUBLISH_CUSTOMER_EXECUTION_20261104_V10'
ACCESSIBLE_PUBLISH_CUSTOMER_REVIEW_BUNDLE = OUTPUT / 'ACCESSIBLE_PUBLISH_CUSTOMER_REVIEW_BUNDLE_20261104_V1'
ACCESSIBLE_PUBLISH_INTERACTION_DEMO = OUTPUT / 'ACCESSIBLE_PUBLISH_CUSTOMER_EXECUTION_20261102_V9'
ACCESSIBLE_PUBLISH_LINK_FORM_DEMO = OUTPUT / 'ACCESSIBLE_PUBLISH_LINK_FORM_DEMO_20261102_V1'
DOCUMENT_STUDIO_EDIT_CUSTOMER_DEMO = OUTPUT / 'DOCUMENT_STUDIO_EDIT_CUSTOMER_EXECUTION_20261106_V2'
DOCUMENT_STUDIO_EDIT_REVIEW_WORKSPACE = DOCUMENT_STUDIO_EDIT_CUSTOMER_DEMO / 'DOCUMENT_STUDIO_EDIT_TECHNICAL_REVIEW.html'
DOCUMENT_STUDIO_EDIT_REVIEW_WORKSPACE_RECEIPT = DOCUMENT_STUDIO_EDIT_CUSTOMER_DEMO / 'DOCUMENT_STUDIO_EDIT_TECHNICAL_REVIEW_RECEIPT.json'
DIO_AI_ASSURANCE_CONTROLLED_EXECUTION = OUTPUT / 'DIO_AI_ASSURANCE_CONTROLLED_EXECUTION_20261101_V1'
DIO_AI_ASSURANCE_TELEMETRY_BINDING_DEMO = OUTPUT / 'DIO_AI_ASSURANCE_TELEMETRY_CASE_BINDING_20261102_V2'
CAMPAIGN_LAB_CUSTOMER_DEMO = OUTPUT / 'CAMPAIGN_LAB_CUSTOMER_EXECUTION_20261102_V2'
CAMPAIGN_LAB_WORKFLOW_DEMO_EVIDENCE = OUTPUT / 'CAMPAIGN_LAB_WORKFLOW_DEMO_REFRESH_20261102_V2.json'
CAMPAIGN_LAB_REVIEW_SURFACE = OUTPUT / 'CAMPAIGN_LAB_REVIEW_SURFACE_20261102_V1'
AGENT_AUTHORITY_CUSTOMER_DEMO = OUTPUT / 'AGENT_AUTHORITY_CUSTOMER_EXECUTION_20261102_V1'
CONTRACTPROOF_CUSTOMER_DEMO = OUTPUT / 'CONTRACTPROOF_CUSTOMER_EXECUTION_20261102_V1'
CHANGEPROOF_CUSTOMER_DEMO = OUTPUT / 'CHANGEPROOF_CUSTOMER_EXECUTION_20261102_V1'
HISTORICAL_CUSTOMER_BATCH = OUTPUT / 'SOURCE_PACKET_CUSTOMER_BATCH_20261102_V1'
OBLIGATION_FAMILY_CUSTOMER_BATCH = OUTPUT / 'OBLIGATION_FAMILY_CUSTOMER_EXECUTIONS_20261102_V1'
OBLIGATION_FAMILY_SOURCE_LOCATION_BATCH = OUTPUT / 'OBLIGATION_FAMILY_CUSTOMER_EXECUTIONS_20261102_V2'
NATIVE_PACKET_CUSTOMER_BATCH = OUTPUT / 'NATIVE_PACKET_CUSTOMER_EXECUTIONS_20261102_V1'
DOSSIEROPS_REVIEW_SURFACE_ROUTE = OUTPUT / 'DOSSIEROPS_REVIEW_SURFACE_ROUTE_20261102_V1'
OPPORTUNITY_FOUNDRY_REVIEW_ROUTE = OUTPUT / 'OPPORTUNITY_FOUNDRY_REVIEW_SURFACE_ROUTE_20261104_V3'
EVIDENCE_PROFILE_REVIEW_SURFACE_BATCH = OUTPUT / 'EVIDENCE_PROFILE_REVIEW_SURFACE_BATCH_20261102_V1'
AI_TRUST_REVIEW_SURFACE_BATCH = OUTPUT / 'AI_TRUST_REVIEW_SURFACES_20261102_V1'
EVIDENCE_PROFILE_REVIEW_SURFACE_PRODUCTS = {
    'HOMS Moderate', 'ProjectProof', 'ImpactProof', 'AuditProof', 'VendorProof', 'DonorProof',
    'ProgrammeProof', 'QualityProof', 'CertificationProof', 'DiligenceRoom', 'AssuranceRoom',
    'ModelProof', 'ReleaseProof', 'AI IncidentRoom', 'CriticalAI Assurance', 'CyberAssurance',
    'ControlDrift', 'SupplierCyberProof', 'IncidentProof', 'DORA Vendor Assurance',
}
VAMP_REVIEW_SURFACE_ROUTES = {
    'VAMP Performance': OUTPUT / 'VAMP_REVIEW_SURFACE_CUSTOMER_ROUTE_20261104_V6/vamp-performance',
    'CPDProof': OUTPUT / 'CPDPROOF_VAMP_REVIEW_SURFACE_20261104_V3',
    'PromotionProof': OUTPUT / 'PROMOTIONPROOF_VAMP_REVIEW_SURFACE_20261104_V3',
}
SOPHIA_SERAPH_PROCESS_PROOF_BATCH = OUTPUT / 'SOPHIA_SERAPH_PROCESS_PROOF_20261102_V2'
SOPHIA_SERAPH_LIVE_PROCESS_BATCH = OUTPUT / 'SOPHIA_SERAPH_PROCESS_PROOF_20261102_V3_LIVE'
SERAPH_TELEMETRY_AI_PROFILE_BATCH = OUTPUT / 'SERAPH_TELEMETRY_AI_PROFILE_EXECUTIONS_20261108_V8'


def read_json(path: Path):
    return json.loads(path.read_text(encoding='utf-8'))


def digest_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open('rb') as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b''):
            digest.update(chunk)
    return digest.hexdigest()


def artifact(path: Path, *, declared_sha256: str | None = None) -> dict:
    path = path.resolve()
    result = {'path': str(path.relative_to(ROOT)), 'exists': path.is_file()}
    if path.is_file():
        result.update(bytes=path.stat().st_size, sha256=digest_file(path))
    if declared_sha256:
        result.update(declared_sha256=declared_sha256,
                      declared_hash_matches=result.get('sha256') == declared_sha256.removeprefix('sha256:'))
    return result


def capability_files(capability_id: str, config: dict) -> list[Path]:
    directory = OUTPUT / config['root']
    if not directory.is_dir():
        raise FileNotFoundError(directory)
    files = sorted(path for path in directory.rglob('*') if path.is_file())
    # Preserve the shared source/custody files, but show only the relevant
    # article/report surfaces for the two capabilities sharing this engine.
    if capability_id in {'report_and_pitch', 'article_preparation'}:
        excluded = {'article'} if capability_id == 'report_and_pitch' else {'report', 'pitch', 'proof'}
        files = [path for path in files if not excluded.intersection(path.relative_to(directory).parts)]
    return files


def build_qualification() -> dict:
    baseline = read_json(BASELINE)
    catalog = customer_product_catalog()
    historical = {row['name']: row for row in baseline['products']}
    if len(historical) != 68 or {row['product_name'] for row in catalog} != set(historical):
        raise ValueError('current catalog and historical 68-offer inventory differ')
    pilot_map = {name: key for key, config in CAPABILITIES.items() for name in config['offers']}
    if len(pilot_map) != 12 or len(CAPABILITIES) != 9:
        raise ValueError('pilot qualification must retain twelve names and nine capabilities')

    evidence_index = {}

    def register(path: Path, declared_sha256=None) -> str:
        value = artifact(path, declared_sha256=declared_sha256)
        previous = evidence_index.get(value['path'], {})
        evidence_index[value['path']] = {**previous, **value}
        return value['path']

    baseline_ref, audit_ref = register(BASELINE), register(AUDIT)
    for path in [ROOT / 'products/customer_product_router.py', ROOT / 'products/customer_specialist_pathways.py',
                 ROOT / 'config/professional_evidence_portfolio/v1/routes.json', Path(__file__),
                 ROOT / 'docs/customer_products/RUNBOOK.md',
                 ROOT / 'cross_folder_variants/NoEdge-Multi-Hymark-main/A_CODE/backend/server.py',
                 ROOT / 'scripts/run_homs_hymark_batch.py',
                 ROOT / 'scripts/audit_homs_assess_point_quote_grounding.py',
                 ROOT / 'scripts/run_homs_assess_pointwise_completeness_v23.py',
                 ROOT / 'scripts/run_homs_assess_tail_recovery_20261102.py',
                 ROOT / 'products/homs_curriculum_grade_spine.py',
                 ROOT / 'scripts/run_homs_curriculum_randomized_grade_spine_batch.py',
                 ROOT / 'products/homs_exam_moderation.py', ROOT / 'products/homs_moderate_customer.py',
                 ROOT / 'scripts/run_homs_moderate_customer_grade_batch.py',
                 ROOT / 'products/accessible_publish.py',
                 ROOT / 'products/accessible_publish_scripted_worker.py',
                 ROOT / 'scripts/run_accessible_publish_semantics_customer_demo.py',
                 ROOT / 'scripts/run_accessible_publish_rendered_customer_demo.py',
                 ROOT / 'products/ai_assurance_customer.py', ROOT / 'products/ai_trust/seraph_telemetry.py',
                 ROOT / 'scripts/run_seraph_telemetry_ai_profile_batch.py',
                 ROOT / 'scripts/run_dio_ai_assurance_telemetry_binding_demo.py',
                 ROOT / 'adapters/lingua/document_translation.py', ROOT / 'adapters/lingua/professional_af_v1.json',
                 ROOT / 'adapters/document_studio/pipeline.py', ROOT / 'products/studio_harvest.py',
                 ROOT / 'products/report_pitch_pipeline.py', ROOT / 'products/customer_specialist_pathways.py',
                 ROOT / 'products/professional_evidence_execution.py', ROOT / 'products/funding_finder_pipeline.py',
                 ROOT / 'scripts/run_article_publication_studio_editorial_surface.py',
                 ROOT / 'scripts/validate_article_publication_editorial_review.py',
                 ROOT / 'scripts/run_correspondence_review_validation_demo.py',
                 ROOT / 'scripts/validate_correspondence_editorial_review.py',
                 ROOT / 'products/customer_launch_pipeline.py',
                 ROOT / 'products/professional_evidence_final_compat.py',
                 ROOT / 'config/customer_products/examples/fundingfinder_opportunities.schema.json',
                 ROOT / 'config/customer_products/examples/launch_brand_asset.schema.json']:
        register(path)
    article_case_root = OUTPUT / 'ARTICLE_PUBLICATION_BYTE_LINEAGE_EXECUTION_20261101_V3/article-publication-studio/article-publication-studio'
    article_review_root = article_case_root / 'EXECUTION/article_publication_studio'
    article_byte_bindings = article_case_root / 'EXECUTION/ARTICLE_SOURCE_BYTE_BINDINGS.json'
    article_editor_bindings = article_case_root / 'EXECUTION/EDITORIAL_CLAIM_SOURCE_BINDINGS.csv'
    article_byte_receipt = article_case_root / 'EXECUTION/ARTICLE_SOURCE_BYTE_BINDINGS_RECEIPT.json'
    article_case_receipt = article_case_root / 'PROFESSIONAL_EVIDENCE_RECEIPT.json'
    if article_byte_receipt.is_file() and article_byte_bindings.is_file() and article_case_receipt.is_file():
        binding_receipt = read_json(article_byte_receipt)
        bindings = read_json(article_byte_bindings)
        case_receipt = read_json(article_case_receipt)
        if (case_receipt.get('status') != 'PASS_FULL_PIPELINE'
                or case_receipt.get('external_publication') != 'REFUSE'
                or case_receipt.get('authority_created') is not False
                or binding_receipt.get('all_source_spans_verified') is not True
                or binding_receipt.get('publication_authorized') is not False
                or binding_receipt.get('bindings_sha256') != hashlib.sha256(article_byte_bindings.read_bytes()).hexdigest()
                or binding_receipt.get('editor_csv_sha256') != hashlib.sha256(article_editor_bindings.read_bytes()).hexdigest()
                or bindings.get('all_source_spans_verified') is not True
                or bindings.get('claim_count') != len(bindings.get('claims') or [])
                or any(row.get('claim_state') != 'CUSTOMER_ASSERTION_UNVERIFIED'
                       or row.get('rights_privacy_and_attribution_review') != 'REQUIRED_PENDING'
                       for row in bindings.get('claims') or [])):
            raise ValueError('Article Publication Studio byte-bound lineage evidence is stale or crossed a review boundary')
    for path in [article_review_root / 'composition/PROOF_MANIFEST.json',
                 article_review_root / 'composition/STUDIO_EXECUTION_RECEIPT.json',
                 article_review_root / 'composition/publication/EDITORIAL_CLAIM_REVIEW_TEMPLATE.csv',
                 article_review_root / 'composition/publication/ARTICLE_LINEAGE_OBJECT.json',
                 article_byte_bindings, article_editor_bindings, article_byte_receipt, article_case_receipt]:
        if path.is_file():
            register(path)
    article_publication_root = OUTPUT / 'ARTICLE_PUBLICATION_BYTE_LINEAGE_20261101_V1/article-publication/article-publication'
    article_publication_execution = article_publication_root / 'EXECUTION/article_publication_studio'
    article_publication_bindings = article_publication_root / 'EXECUTION/ARTICLE_SOURCE_BYTE_BINDINGS.json'
    article_publication_editor_bindings = article_publication_root / 'EXECUTION/EDITORIAL_CLAIM_SOURCE_BINDINGS.csv'
    article_publication_binding_receipt = article_publication_root / 'EXECUTION/ARTICLE_SOURCE_BYTE_BINDINGS_RECEIPT.json'
    article_publication_case_receipt = article_publication_root / 'PROFESSIONAL_EVIDENCE_RECEIPT.json'
    if (article_publication_binding_receipt.is_file() and article_publication_bindings.is_file()
            and article_publication_editor_bindings.is_file() and article_publication_case_receipt.is_file()):
        binding_receipt = read_json(article_publication_binding_receipt)
        bindings = read_json(article_publication_bindings)
        case_receipt = read_json(article_publication_case_receipt)
        if (case_receipt.get('status') != 'PASS_FULL_PIPELINE'
                or case_receipt.get('external_publication') != 'REFUSE'
                or binding_receipt.get('all_source_spans_verified') is not True
                or binding_receipt.get('publication_authorized') is not False
                or binding_receipt.get('bindings_sha256') != hashlib.sha256(article_publication_bindings.read_bytes()).hexdigest()
                or binding_receipt.get('editor_csv_sha256') != hashlib.sha256(article_publication_editor_bindings.read_bytes()).hexdigest()
                or bindings.get('all_source_spans_verified') is not True
                or any(row.get('claim_state') != 'CUSTOMER_ASSERTION_UNVERIFIED'
                       or row.get('rights_privacy_and_attribution_review') != 'REQUIRED_PENDING'
                       for row in bindings.get('claims') or [])):
            raise ValueError('Article Publication byte-bound lineage evidence is stale or crossed a publication boundary')
    for path in [article_publication_case_receipt, article_publication_bindings,
                 article_publication_editor_bindings, article_publication_binding_receipt,
                 article_publication_execution / 'composition/PROOF_MANIFEST.json',
                 article_publication_execution / 'composition/publication/ARTICLE_LINEAGE_OBJECT.json',
                 article_publication_execution / 'composition/STUDIO_EXECUTION_RECEIPT.json']:
        if path.is_file():
            register(path)
    report_pitch_root = OUTPUT / 'REPORT_PITCH_REVIEW_WORKSHEET_20261106'
    for path in [report_pitch_root / 'EDITORIAL_REVIEW_WORKSHEET.csv',
                 report_pitch_root / 'package_manifest.json', report_pitch_root / 'reviewer_checklist.json',
                 report_pitch_root / 'controlled_review_package.zip']:
        if path.is_file():
            register(path)
    correspondence_root = OUTPUT / 'PROFESSIONAL_CORRESPONDENCE_RECORD_BOUND_20261106_V2/professional-correspondence/professional-correspondence'
    for path in [correspondence_root / 'PROFESSIONAL_EVIDENCE_RECEIPT.json',
                 correspondence_root / 'EXECUTION/professional_correspondence/CORRESPONDENCE_EDITOR_REVIEW.csv',
                 correspondence_root / 'EXECUTION/professional_correspondence/CORRESPONDENCE_SOURCE_MAP.json',
                 correspondence_root / 'EXECUTION/professional_correspondence/DRAFT_CORRESPONDENCE.txt',
                 correspondence_root / 'EXECUTION/professional_correspondence/CUSTOMER_PACKAGE_RECEIPT.json']:
        if path.is_file():
            register(path)
    correspondence_lineage_root = OUTPUT / 'PROFESSIONAL_CORRESPONDENCE_BYTE_LINEAGE_20261101_V3/professional-correspondence/professional-correspondence'
    correspondence_byte_bindings = correspondence_lineage_root / 'EXECUTION/professional_correspondence/CORRESPONDENCE_SOURCE_BYTE_BINDINGS.json'
    correspondence_byte_receipt = correspondence_lineage_root / 'EXECUTION/professional_correspondence/CORRESPONDENCE_SOURCE_BYTE_BINDINGS_RECEIPT.json'
    correspondence_case_receipt = correspondence_lineage_root / 'PROFESSIONAL_EVIDENCE_RECEIPT.json'
    if correspondence_byte_bindings.is_file() and correspondence_byte_receipt.is_file() and correspondence_case_receipt.is_file():
        bindings = read_json(correspondence_byte_bindings)
        binding_receipt = read_json(correspondence_byte_receipt)
        case_receipt = read_json(correspondence_case_receipt)
        if (case_receipt.get('status') != 'PASS_FULL_PIPELINE'
                or case_receipt.get('external_send') != 'REFUSE'
                or binding_receipt.get('source_register_bytes_verified') is not True
                or binding_receipt.get('all_bindings_have_register_identity') is not True
                or binding_receipt.get('customer_statements_verified') is not False
                or binding_receipt.get('external_send_authorized') is not False
                or not bindings.get('bindings')
                or any(row.get('statement_state') != 'CUSTOMER_ASSERTION_UNVERIFIED'
                       or row.get('editorial_review_required') is not True
                       for row in bindings.get('bindings') or [])):
            raise ValueError('Professional Correspondence byte-bound source lineage is stale or crossed a review boundary')
    for path in [correspondence_lineage_root / 'PROFESSIONAL_EVIDENCE_RECEIPT.json',
                 correspondence_byte_bindings, correspondence_byte_receipt,
                 correspondence_lineage_root / 'EXECUTION/professional_correspondence/CORRESPONDENCE_EDITOR_REVIEW.csv',
                 correspondence_lineage_root / 'EXECUTION/professional_correspondence/CUSTOMER_PACKAGE_RECEIPT.json']:
        if path.is_file():
            register(path)
    contract_lineage_root = OUTPUT / 'CONTRACT_DESK_SOURCE_LINEAGE_VALIDATION_20261101_V1/contract-desk/contract-desk'
    contract_lineage_validation = contract_lineage_root / 'EXECUTION/contract_desk/SOURCE_LINEAGE_VALIDATION_RECEIPT.json'
    contract_case_receipt = contract_lineage_root / 'PROFESSIONAL_EVIDENCE_RECEIPT.json'
    contract_date_scenario_root = OUTPUT / 'CONTRACT_DESK_CONDITIONAL_DATES_20261104_V3'
    contract_date_scenarios = contract_date_scenario_root / 'DEADLINE_SCENARIOS.json'
    contract_date_receipt = contract_date_scenario_root / 'CONDITIONAL_DATE_SCENARIO_RECEIPT.json'
    contract_worksheet_root = contract_date_scenario_root
    contract_worksheet_receipt = contract_worksheet_root / 'CUSTOMER_PACKAGE_RECEIPT.json'
    contract_worksheet = contract_worksheet_root / 'REVIEW_WORKSHEET.json'
    regops_review_root = OUTPUT / 'DIO_REGOPS_CUSTOMER_REVIEW_REGISTER_20261104_V3/dio-regops/dio-regops/dio-regops'
    regops_review_pack = regops_review_root / 'EXECUTION/REGOPS_READINESS_PACK.json'
    regops_review_receipt = regops_review_root / 'PROFESSIONAL_EVIDENCE_RECEIPT.json'
    regops_processing_receipt = regops_review_root / 'EXECUTION/REGOPS_PROCESSING_RECEIPT.json'
    regops_review_register = regops_review_root / 'EXECUTION/REGOPS_CUSTOMER_REVIEW_REGISTER.csv'
    regops_review_source = regops_review_root / 'CUSTOMER_PACKET/SOURCES/02_evidence_register.csv'
    if contract_lineage_validation.is_file() and contract_case_receipt.is_file():
        validation = read_json(contract_lineage_validation)
        case_receipt = read_json(contract_case_receipt)
        if (case_receipt.get('status') != 'PASS_FULL_PIPELINE'
                or validation.get('source_file_matches_customer_packet') is not True
                or validation.get('all_clause_byte_spans_match_exact_source') is not True
                or validation.get('all_extracted_obligations_bind_to_exact_clause') is not True
                or validation.get('legal_interpretation_or_statement_truth_verified') is not False
                or validation.get('professional_approval') != 'NOT_GRANTED'):
            raise ValueError('Contract Desk source lineage validation is stale or crossed a legal review boundary')
    for path in [contract_case_receipt, contract_lineage_validation,
                 contract_lineage_root / 'EXECUTION/contract_desk/SOURCE_LINEAGE.json',
                 contract_lineage_root / 'EXECUTION/contract_desk/OBLIGATION_BUNDLE.json',
                 contract_lineage_root / 'EXECUTION/contract_desk/CUSTOMER_PACKAGE_RECEIPT.json']:
        if path.is_file():
            register(path)
    fundingfinder_roots = [
        OUTPUT / 'FUNDINGFINDER_CUSTOMER_ROUTE_SNAPSHOT_20261106_V1',
        OUTPUT / 'FUNDINGFINDER_PUBLIC_ROUTE_20261106_V1',
        OUTPUT / 'FUNDINGFINDER_RAW_PACKET_OFFLINE_EXECUTION_20261101',
    ]
    for funding_root in fundingfinder_roots:
        for relative in ('CUSTOMER_EXECUTION_RECEIPT.json', 'package_manifest.json', 'source_register.json',
                         'eligibility_matrix.json', 'FUNDINGFINDER_INPUT_BINDING.json',
                         'EXECUTION/FUNDINGFINDER_INPUT_BINDING.json',
                         'EXECUTION/fundingfinder/package_manifest.json',
                         'EXECUTION/fundingfinder/source_register.json',
                         'EXECUTION/fundingfinder/eligibility_matrix.json',
                         'CUSTOMER_PACKET/SOURCES/04_official_opportunities.json'):
            path = funding_root / relative
            if path.is_file():
                register(path)
    finance_root = OUTPUT / 'FINANCE_READINESS_RECONCILIATION_20261101_V1/finance-readiness/finance-readiness'
    for path in [finance_root / 'PROFESSIONAL_EVIDENCE_RECEIPT.json',
                 finance_root / 'EXECUTION/finance_readiness/CUSTOMER_AMOUNT_RECONCILIATION.json',
                 finance_root / 'EXECUTION/finance_readiness/CUSTOMER_PACKAGE_RECEIPT.json',
                 finance_root / 'EXECUTION/finance_readiness/SOURCE_BINDINGS.json',
                 finance_root / 'EXECUTION/finance_readiness/READINESS_EVIDENCE_MATRIX.json']:
        if path.is_file():
            register(path)
    finance_studio_root = OUTPUT / 'FINANCE_READINESS_STUDIO_RECONCILIATION_20261101_V2/finance-readiness-studio/finance-readiness-studio'
    for path in [finance_studio_root / 'PROFESSIONAL_EVIDENCE_RECEIPT.json',
                 finance_studio_root / 'EXECUTION/finance_readiness_studio/FINANCE_READINESS_STUDIO_SOURCE_BINDINGS.json',
                 finance_studio_root / 'EXECUTION/finance_readiness_studio/FINANCE_READINESS_STUDIO_SOURCE_BINDINGS_RECEIPT.json',
                 finance_studio_root / 'EXECUTION/finance_readiness_studio/composition/finance/FINANCE_READINESS_OBJECT.json',
                 finance_studio_root / 'EXECUTION/finance_readiness_studio/composition/finance/READINESS_REPORT.html']:
        if path.is_file():
            register(path)
    finance_studio_validation_root = OUTPUT / 'FINANCE_READINESS_STUDIO_SOURCE_VALIDATION_20261101_V1/finance-readiness-studio/finance-readiness-studio'
    finance_studio_validation = finance_studio_validation_root / 'EXECUTION/FINANCE_READINESS_STUDIO_SOURCE_VALIDATION_RECEIPT.json'
    finance_studio_case_receipt = finance_studio_validation_root / 'PROFESSIONAL_EVIDENCE_RECEIPT.json'
    if finance_studio_validation.is_file() and finance_studio_case_receipt.is_file():
        validation = read_json(finance_studio_validation)
        case_receipt = read_json(finance_studio_case_receipt)
        reconciliation = validation.get('amount_reconciliation') or {}
        if (case_receipt.get('status') != 'PASS_FULL_PIPELINE'
                or validation.get('verified_record_count', 0) < 1
                or validation.get('all_record_spans_match_exact_register_bytes') is not True
                or validation.get('all_statement_hashes_match') is not True
                or reconciliation.get('state') != 'RECOMPUTED_FROM_CUSTOMER_ASSERTIONS'
                or reconciliation.get('arithmetic_variance') is None
                or validation.get('customer_statement_truth_verified') is not False
                or validation.get('lender_eligibility_or_approval') != 'NOT_DETERMINED'):
            raise ValueError('Finance Readiness Studio source validation is stale or crossed its lender decision boundary')
    for path in [finance_studio_case_receipt, finance_studio_validation,
                 finance_studio_validation_root / 'EXECUTION/FINANCE_READINESS_STUDIO_SOURCE_BINDINGS.json',
                 finance_studio_validation_root / 'EXECUTION/FINANCE_READINESS_STUDIO_SOURCE_BINDINGS_RECEIPT.json',
                 finance_studio_validation_root / 'EXECUTION/finance_readiness_studio/composition/finance/FINANCE_READINESS_OBJECT.json']:
        if path.is_file():
            register(path)
    finance_studio_amount_root = OUTPUT / 'FINANCE_READINESS_STUDIO_AMOUNT_SPAN_BINDINGS_20261102_V3/finance-readiness-studio/finance-readiness-studio'
    finance_studio_amount_case = finance_studio_amount_root / 'PROFESSIONAL_EVIDENCE_RECEIPT.json'
    finance_studio_amount_validation = finance_studio_amount_root / 'EXECUTION/FINANCE_READINESS_STUDIO_SOURCE_VALIDATION_RECEIPT.json'
    finance_studio_amount_spans = finance_studio_amount_root / 'EXECUTION/FINANCE_READINESS_STUDIO_AMOUNT_SPAN_BINDINGS.json'
    if finance_studio_amount_case.is_file() and finance_studio_amount_validation.is_file() and finance_studio_amount_spans.is_file():
        route = read_json(finance_studio_amount_case)
        validation = read_json(finance_studio_amount_validation)
        spans = read_json(finance_studio_amount_spans)
        bound_spans = spans.get('bindings') or []
        if (route.get('status') != 'PASS_FULL_PIPELINE'
                or validation.get('all_amount_spans_match_exact_register_bytes') is not True
                or len(bound_spans) != 3
                or any(not row.get('source_phrase_sha256') or not row.get('source_row_sha256')
                       or not row.get('source_file_sha256') for row in bound_spans)
                or spans.get('source_register_sha256') != validation.get('source_register_sha256')
                or spans.get('human_review_required') is not True):
            raise ValueError('Finance Readiness Studio amount spans are stale or not bound to the verified source register')
        for path in [finance_studio_amount_case, finance_studio_amount_validation, finance_studio_amount_spans]:
            register(path)
    finance_currency_evidence = OUTPUT / 'FINANCE_READINESS_CURRENCY_RECONCILIATION_20261102_V2/FINANCE_READINESS_CURRENCY_RECONCILIATION_EVIDENCE.json'
    if finance_currency_evidence.is_file():
        currency_receipt = read_json(finance_currency_evidence)
        currency_result = currency_receipt.get('reconciliation') or {}
        if (currency_receipt.get('synthetic_route_execution') is not True
                or currency_result.get('state') != 'MIXED_CURRENCY_REVIEW_REQUIRED'
                or currency_result.get('difference') is not None
                or currency_result.get('currency_code') is not None
                or currency_receipt.get('release_authorized') is not False):
            raise ValueError('Finance Readiness currency reconciliation evidence is invalid or calculates across currencies')
        register(finance_currency_evidence)
    finance_binding_root = OUTPUT / 'FINANCE_READINESS_BYTE_BINDING_VALIDATION_20261101_V1/finance-readiness/finance-readiness'
    finance_binding_validation = finance_binding_root / 'EXECUTION/finance_readiness/SOURCE_BINDINGS_VALIDATION_RECEIPT.json'
    finance_binding_case_receipt = finance_binding_root / 'PROFESSIONAL_EVIDENCE_RECEIPT.json'
    if finance_binding_validation.is_file() and finance_binding_case_receipt.is_file():
        validation = read_json(finance_binding_validation)
        case_receipt = read_json(finance_binding_case_receipt)
        if (case_receipt.get('status') != 'PASS_FULL_PIPELINE'
                or validation.get('all_customer_row_spans_match_exact_register_bytes') is not True
                or validation.get('all_quoted_customer_statements_match_their_register_rows') is not True
                or validation.get('customer_statement_truth_verified') is not False
                or validation.get('financial_conclusions_or_lender_eligibility_verified') is not False
                or validation.get('professional_approval') != 'NOT_GRANTED'):
            raise ValueError('Finance Readiness byte-bound source review evidence is stale or crossed a review boundary')
    for path in [finance_binding_case_receipt, finance_binding_validation,
                 finance_binding_root / 'EXECUTION/finance_readiness/SOURCE_BINDINGS.json',
                 finance_binding_root / 'EXECUTION/finance_readiness/READINESS_EVIDENCE_MATRIX.json',
                 finance_binding_root / 'EXECUTION/finance_readiness/CUSTOMER_PACKAGE_RECEIPT.json']:
        if path.is_file():
            register(path)
    report_pitch_lineage_root = OUTPUT / 'REPORT_PITCH_SOURCE_BYTE_LINEAGE_20261102_V2/report-pitch-studio/report-pitch-studio'
    report_pitch_review_evidence = OUTPUT / 'REPORT_PITCH_SOURCE_BYTE_LINEAGE_20261102_V2/REPORT_PITCH_EDITORIAL_REVIEW_SURFACE_EVIDENCE.json'
    report_pitch_bindings = report_pitch_lineage_root / 'EXECUTION/report_pitch_studio/REPORT_PITCH_SOURCE_BYTE_BINDINGS.json'
    report_pitch_bindings_receipt = report_pitch_lineage_root / 'EXECUTION/report_pitch_studio/REPORT_PITCH_SOURCE_BYTE_BINDINGS_RECEIPT.json'
    report_pitch_case_receipt = report_pitch_lineage_root / 'PROFESSIONAL_EVIDENCE_RECEIPT.json'
    if report_pitch_bindings.is_file() and report_pitch_bindings_receipt.is_file() and report_pitch_case_receipt.is_file():
        bindings = read_json(report_pitch_bindings)
        binding_receipt = read_json(report_pitch_bindings_receipt)
        case_receipt = read_json(report_pitch_case_receipt)
        if (case_receipt.get('status') != 'PASS_FULL_PIPELINE'
                or case_receipt.get('external_publication') != 'REFUSE'
                or binding_receipt.get('source_register_bytes_verified') is not True
                or binding_receipt.get('all_claims_bind_to_exact_customer_register_rows') is not True
                or binding_receipt.get('customer_claims_verified') is not False
                or binding_receipt.get('publication_authorized') is not False
                or not bindings.get('bindings')
                or any(row.get('customer_statement_verified') is not False
                       or row.get('editorial_review_required') is not True
                       for row in bindings.get('bindings') or [])):
            raise ValueError('Report & Pitch Studio source-byte lineage is stale or crossed a publication boundary')
    for path in [report_pitch_case_receipt, report_pitch_bindings, report_pitch_bindings_receipt,
                 report_pitch_lineage_root / 'EXECUTION/report_pitch_studio/EDITORIAL_REVIEW_WORKSHEET.csv',
                 report_pitch_lineage_root / 'EXECUTION/report_pitch_studio/package_manifest.json',
                 report_pitch_lineage_root / 'EXECUTION/report_pitch_studio/controlled_review_package.zip']:
        if path.is_file():
            register(path)
    report_pitch_visual_review = OUTPUT / 'report-pitch/reviewed-final-v4/baseline/REPORT_PITCH_VISUAL_REVIEW.json'
    if report_pitch_visual_review.is_file():
        register(report_pitch_visual_review)
    investorproof_root = OUTPUT / 'INVESTORPROOF_SOURCE_AMOUNT_VALIDATION_20261101_V2/investorproof/investorproof'
    investorproof_validation = investorproof_root / 'EXECUTION/investorproof/INVESTORPROOF_SOURCE_AMOUNT_VALIDATION_RECEIPT.json'
    investorproof_case_receipt = investorproof_root / 'PROFESSIONAL_EVIDENCE_RECEIPT.json'
    if investorproof_validation.is_file() and investorproof_case_receipt.is_file():
        validation = read_json(investorproof_validation)
        case_receipt = read_json(investorproof_case_receipt)
        if (case_receipt.get('status') != 'PASS_FULL_PIPELINE'
                or validation.get('verified_amount_count') != 6
                or validation.get('all_amounts_match_exact_register_row_label_currency_and_value') is not True
                or validation.get('metrics_recomputed_from_source_bound_amounts') is not True
                or validation.get('customer_workbook_matches_recomputed_metrics') is not True
                or validation.get('customer_statements_or_financial_truth_verified') is not False
                or validation.get('audit_or_investor_approval') != 'NOT_GRANTED'):
            raise ValueError('InvestorProof financial lineage evidence is stale or crossed a review boundary')
    for path in [investorproof_case_receipt, investorproof_validation,
                 investorproof_root / 'EXECUTION/investorproof/FINANCIAL_REVIEW_WORKBOOK.xlsx',
                 investorproof_root / 'EXECUTION/investorproof/FINANCIAL_SOURCE_BINDINGS.json',
                 investorproof_root / 'EXECUTION/investorproof/CUSTOMER_PACKAGE_RECEIPT.json']:
        if path.is_file():
            register(path)
    vamp_window_root = OUTPUT / 'VAMP_REVIEW_WINDOW_BYTE_BINDING_20261101_V1/vamp-performance/vamp-performance'
    vamp_window_binding = vamp_window_root / 'EXECUTION/VAMP_CUSTOMER_SNAPSHOT_BINDING.json'
    vamp_window_case_receipt = vamp_window_root / 'PROFESSIONAL_EVIDENCE_RECEIPT.json'
    if vamp_window_binding.is_file() and vamp_window_case_receipt.is_file():
        binding = read_json(vamp_window_binding)
        case_receipt = read_json(vamp_window_case_receipt)
        period_binding = binding.get('review_window_source_binding') or {}
        if (case_receipt.get('status') != 'PASS_FULL_PIPELINE'
                or period_binding.get('exact_register_bytes_verified') is not True
                or period_binding.get('source_file_sha256') != binding.get('source_register_sha256')
                or binding.get('snapshot_window_matches_customer_scope') is not True
                or binding.get('source_rows_match_snapshot') is not True
                or binding.get('rating_generated') is not False
                or binding.get('human_review_required') is not True):
            raise ValueError('VAMP Performance declared review-window evidence is stale or crossed a rating boundary')
    for path in [vamp_window_case_receipt, vamp_window_binding]:
        if path.is_file():
            register(path)
    vamp_objective_mapping_root = OUTPUT / 'VAMP_JAN_JUNE_OBJECTIVE_MAPPING_20261102_V6'
    vamp_objective_mapping_package = vamp_objective_mapping_root / 'CUSTOMER_PACKAGE_RECEIPT.json'
    vamp_objective_mapping_projection = vamp_objective_mapping_root / 'PROJECTION/VAMP_DOMAIN_PROJECTION.json'
    vamp_objective_mapping_validation = vamp_objective_mapping_root / 'VAMP_CUSTOMER_SOURCE_MAPPING_VALIDATION.json'
    vamp_objective_mapping_snapshot = next(iter((vamp_objective_mapping_root / 'native_vamp').glob('*/VAMP_SNAPSHOT.json')), Path('/missing')) if (vamp_objective_mapping_root / 'native_vamp').is_dir() else Path('/missing')
    vamp_objective_mapping_case_source = OUTPUT / 'VAMP_REVIEW_WINDOW_BYTE_BINDING_20261101_V1/vamp-performance/vamp-performance/CUSTOMER_PACKET/SOURCES/02_evidence_register.csv'
    if vamp_objective_mapping_package.is_file() and vamp_objective_mapping_projection.is_file() and vamp_objective_mapping_validation.is_file() and vamp_objective_mapping_snapshot.is_file() and vamp_objective_mapping_case_source.is_file():
        mapping_package = read_json(vamp_objective_mapping_package)
        mapping_projection = read_json(vamp_objective_mapping_projection)
        mapping_validation = read_json(vamp_objective_mapping_validation)
        mapping_snapshot = read_json(vamp_objective_mapping_snapshot)
        source_bytes = vamp_objective_mapping_case_source.read_bytes()
        source_sha = hashlib.sha256(source_bytes).hexdigest()
        objective_codes = {match.group(0) for row in mapping_snapshot.get('objectives', [])
                           if (match := re.search(r'\bKPA\d+\b', str(row.get('title') or '')))}
        candidate_rows = [row for row in mapping_projection.get('rows', []) if row.get('candidate_task_id')]
        span_checks = []
        for row in mapping_projection.get('rows', []):
            binding = row.get('source_binding') or {}
            start, end = int(binding.get('source_byte_start', -1)), int(binding.get('source_byte_end_exclusive', -1))
            statement = str(row.get('record') or '')
            span_checks.append(start >= 0 and end >= start and end <= len(source_bytes)
                               and source_bytes[start:end].decode('utf-8') == statement
                               and binding.get('source_file_sha256') == source_sha
                               and binding.get('source_statement_sha256') == hashlib.sha256(statement.encode('utf-8')).hexdigest())
        if (mapping_package.get('product_name') != 'VAMP Performance'
                or mapping_package.get('review_window', {}).get('months') != [f'2026-{month:02d}' for month in range(1, 7)]
                or mapping_package.get('objective_count') != 3
                or mapping_package.get('candidate_source_mapping_count') != 3
                or mapping_package.get('coverage_metrics', {}).get('accepted_mappings') != 0
                or mapping_package.get('coverage_metrics', {}).get('candidate_mappings') != 3
                or objective_codes != {'KPA1', 'KPA3', 'KPA5'}
                or {row.get('record_id') for row in candidate_rows} != {'R-02', 'R-03', 'R-04'}
                or any(row.get('candidate_mapping_state') != 'CANDIDATE_PENDING_HUMAN_REVIEW' for row in candidate_rows)
                or mapping_validation.get('exact_projection_byte_spans_verified') is not True
                or mapping_validation.get('source_bound_projection_row_count') != 6
                or mapping_validation.get('customer_statement_truth_verified') is not False
                or mapping_validation.get('rating_generated') is not False
                or mapping_validation.get('human_review_required') is not True
                or not span_checks or not all(span_checks)):
            raise ValueError('VAMP objective mapping route failed its source-bound, review-held evidence checks')
        for path in [vamp_objective_mapping_package, vamp_objective_mapping_projection, vamp_objective_mapping_validation,
                     vamp_objective_mapping_snapshot, vamp_objective_mapping_root / 'REVIEW_CONTENT.json',
                     vamp_objective_mapping_case_source]:
            register(path)
    for product, folder, prefix in [
        ('CPDProof', 'CPDPROOF_SOURCE_ATTACHED_REVIEW_20261101_V3', 'CPDPROOF'),
        ('PromotionProof', 'PROMOTIONPROOF_ATTACHMENT_BINDING_DEMO_20261101_V3', 'PROMOTIONPROOF'),
    ]:
        review_root = OUTPUT / folder
        for path in [review_root / 'EXECUTION/NATIVE_CUSTOMER_PACKET_RECEIPT.json',
                     review_root / f'EXECUTION/EXECUTION/profile_review/{prefix}_REVIEW_PACK.json',
                     review_root / f'EXECUTION/EXECUTION/profile_review/{prefix}_REVIEW_PACK.html',
                     review_root / 'EXECUTION/CUSTOMER_PACKET/CUSTOMER_PACKET_MANIFEST.json']:
            if path.is_file():
                register(path)
    launch_root = OUTPUT / 'LAUNCH_STUDIO_CUSTOMER_ASSET_REFRESH_20261101_V1/launch-studio/launch-studio'
    for path in [launch_root / 'PROFESSIONAL_EVIDENCE_RECEIPT.json',
                 launch_root / 'EXECUTION/launch_studio/package_manifest.json',
                 launch_root / 'EXECUTION/launch_studio/review/source_semantic_manifest.json',
                 launch_root / 'EXECUTION/launch_studio/review/reviewer_checklist.json']:
        if path.is_file():
            register(path)
    launch_asset_root = OUTPUT / 'LAUNCH_STUDIO_SUPPLIED_ASSET_PACKET_20261101_V1'
    for path in [launch_asset_root / 'CUSTOMER_PACKET/CUSTOMER_PACKET_MANIFEST.json',
                 launch_asset_root / 'CUSTOMER_PACKET/SOURCES/04_brand_asset.json',
                 launch_asset_root / 'CUSTOMER_PACKET/SOURCES/customer-brand-synthetic-validation.png',
                 launch_asset_root / 'EXECUTION/launch_studio/package_manifest.json',
                 launch_asset_root / 'EXECUTION/launch_studio/review/source_semantic_manifest.json',
                 launch_asset_root / 'EXECUTION/launch_studio/review/reviewer_checklist.json']:
        if path.is_file():
            register(path)
    launch_binding_root = LAUNCH_STUDIO_RENDERED_SOURCE_BINDING
    for path in [launch_binding_root / 'package_manifest.json',
                 launch_binding_root / 'review/SOURCE_BINDING_RECEIPT.json',
                 launch_binding_root / 'review/source_semantic_manifest.json',
                 launch_binding_root / 'channel_copy.json',
                 launch_binding_root / 'landing.html',
                 launch_binding_root / 'launch_schedule.json']:
        if path.is_file():
            register(path)
    vamp_root = OUTPUT / 'VAMP_PERFORMANCE_REVIEW_WINDOW_RECONCILIATION_20261101_V2/vamp-performance/vamp-performance'
    for path in [vamp_root / 'PROFESSIONAL_EVIDENCE_RECEIPT.json',
                 vamp_root / 'PROJECTION/VAMP_SNAPSHOT_REQUEST.json',
                 vamp_root / 'PROJECTION/VAMP_DOMAIN_PROJECTION.json',
                 vamp_root / 'EXECUTION/VAMP_CUSTOMER_SNAPSHOT_BINDING.json',
                 vamp_root / 'EXECUTION/PROFESSIONAL_VAMP_PIPELINE_RECEIPT.json',
                 vamp_root / 'EXECUTION/vamp_snapshot/PRO-VAMP-PERFORMANCE/VAMP_SNAPSHOT.json']:
        if path.is_file():
            register(path)
    focused_log = OUTPUT / 'FOCUSED_FINAL_TESTS.log'
    if focused_log.is_file():
        register(focused_log)

    fresh_by_offer, run_groups = {}, {}
    for group_id, relative in RUN_GROUPS.items():
        receipt_path = OUTPUT / relative / RUN_RECEIPT
        receipt = read_json(receipt_path)
        receipt_ref = register(receipt_path)
        run_groups[group_id] = {
            'source': receipt_ref, 'generated_at': receipt.get('generated_at'),
            'journey_count': receipt['journey_count'],
            'verified_journey_count': receipt['verified_journey_count'],
            'refused_journey_count': receipt['refused_journey_count'],
            'boundary': 'Mechanical source/custody and held-output execution evidence; no independent professional acceptance.',
        }
        for name, item in receipt['by_incarnation'].items():
            fresh_by_offer[name] = {
                'evidence_group': group_id, 'receipt': receipt_ref,
                'executed_at': receipt.get('generated_at'),
                'verified_count': item['verified_count'], 'variant_count': item['variant_count'],
                'all_variants_verified': item['all_variants_verified'],
                'variants': item['variants'],
            }

    # The latest 53 canonical plus 15 supplemental route runs are newer than
    # the original pilot-only run groups above. Verify their linked receipt
    # hashes before treating them as current route execution evidence.
    full_portfolio = None
    full_by_offer = {}
    native_extension_batch = None
    native_extension_names = set()
    if NATIVE_EXTENSION_BATCH.is_file() and NATIVE_EXTENSION_MATERIALIZATION.is_file():
        batch = read_json(NATIVE_EXTENSION_BATCH)
        materialization = read_json(NATIVE_EXTENSION_MATERIALIZATION)
        if (batch.get('acceptance_token') != 'DIO_CANON_EXTENSION_NATIVE_PRODUCT_GRADE_VERIFIED'
                or batch.get('all_verified') is not True or batch.get('verified_count') != 11
                or batch.get('refuse_count') != 0 or batch.get('commercial_validation') != 'UNPROVED'):
            raise ValueError('current native canon-extension batch is not a complete verified batch')
        if len(batch.get('products', {})) != 11:
            raise ValueError('native canon-extension batch does not contain exactly eleven products')
        batch_ref = register(NATIVE_EXTENSION_BATCH)
        materialization_ref = register(NATIVE_EXTENSION_MATERIALIZATION)
        native_extension_names = set(batch['products'])
        native_extension_batch = {
            'source': batch_ref, 'materialization_source': materialization_ref,
            'schema': batch['schema'], 'verified_count': batch['verified_count'],
            'target_count': batch['target_count'], 'refuse_count': batch['refuse_count'],
            'batch_fingerprint': batch['batch_fingerprint'],
            'claim_boundary': batch['claim_boundary'],
        }
        run_groups['current_native_canon_extension_product_grade'] = {
            **native_extension_batch,
            'journey_count': batch['target_count'],
            'verified_journey_count': batch['verified_count'],
            'refused_journey_count': batch['refuse_count'],
            'boundary': batch['claim_boundary'],
        }
    fundingfinder_v6 = FUNDING_FINDER_SERVICESETA_ROUTE
    fundingfinder_receipt_path = fundingfinder_v6 / 'CUSTOMER_EXECUTION_RECEIPT.json'
    fundingfinder_packet_path = FUNDING_FINDER_SERVICESETA_PACKET
    fundingfinder_evidence_path = FUNDING_FINDER_SERVICESETA_EVIDENCE
    if fundingfinder_receipt_path.is_file() and fundingfinder_packet_path.is_file() and fundingfinder_evidence_path.is_file():
        execution = read_json(fundingfinder_receipt_path)
        receipt = execution.get('receipt') or {}
        rows = receipt.get('shortlist') or []
        if (execution.get('requested_product') != 'FundingFinder' or len(rows) != 1
                or rows[0].get('fit_state') != 'unknown_review_required'
                or rows[0].get('timing_state') != 'within_stated_deadline'
                or execution.get('release_authorized') is not False
                or execution.get('external_effects') is not False):
            raise ValueError('FundingFinder live Services SETA route failed its held-route contract')
        source_register = read_json(fundingfinder_v6 / 'source_register.json')
        supporting = source_register.get('supporting_sources') or []
        if {row.get('source_id') for row in supporting} != {'DG03-UPDATE', 'DG-ADVERT', 'ANNEXURE-A', 'EVALUATION'}:
            raise ValueError('FundingFinder live route is missing a required official supporting document')
        report_files = list((fundingfinder_v6 / 'report').glob('funding-*-english.pdf')) + list((fundingfinder_v6 / 'report').glob('funding-*-english.docx')) + list((fundingfinder_v6 / 'report').glob('funding-*-english.html'))
        if len(report_files) != 3:
            raise ValueError('FundingFinder live route must include PDF, DOCX and HTML customer reports')
        route_refs = [register(fundingfinder_receipt_path), register(fundingfinder_packet_path), register(fundingfinder_evidence_path),
                      register(fundingfinder_v6 / 'source_register.json'), register(fundingfinder_v6 / 'eligibility_matrix.json'),
                      *(register(path) for path in report_files),
                      register(fundingfinder_v6 / 'controlled_funding_review.zip'), register(fundingfinder_v6 / 'package_manifest.json')]
        for source in supporting:
            raw_file = ROOT / fundingfinder_v6 / source['raw_path']
            text_file = ROOT / fundingfinder_v6 / source['text_path']
            register(raw_file, source['sha256'])
            register(text_file, source['visible_text_sha256'])
        run_groups['fundingfinder_live_services_seta_refresh'] = {
            'source': register(fundingfinder_evidence_path), 'route_receipt': register(fundingfinder_receipt_path),
            'journey_count': 1, 'verified_journey_count': 1, 'refused_journey_count': 0,
            'supporting_official_document_count': len(supporting),
            'deadline': rows[0].get('deadline'), 'fit_state': rows[0].get('fit_state'),
            'boundary': 'Fresh official-source capture and artifact hashes verified. Synthetic applicant eligibility remains unresolved; no award, submission or external release is asserted.',
        }

    evidex_attachment_evidence = OUTPUT / 'EVIDEX_ATTACHED_SOURCE_DEMO_20261102_V1.json'
    evidex_attachment_receipt = EVIDEX_ATTACHED_SOURCE_DEMO / 'CUSTOMER_EXECUTION_RECEIPT.json'
    evidex_attachment_manifest = EVIDEX_ATTACHED_SOURCE_DEMO / 'EVIDEX_SOURCE_FILE_MANIFEST.json'
    if evidex_attachment_evidence.is_file() and evidex_attachment_receipt.is_file() and evidex_attachment_manifest.is_file():
        evidence = read_json(evidex_attachment_evidence)
        receipt = read_json(evidex_attachment_receipt)
        manifest = read_json(evidex_attachment_manifest)
        files = manifest.get('files') or []
        if (evidence.get('schema') != 'dio.evidex.attached_source_execution.v1'
                or evidence.get('product') != 'Evidex EvidenceOps'
                or evidence.get('attachment_count') != 3 or len(files) != 3
                or evidence.get('all_output_hashes_verified') is not True
                or evidence.get('support_adjudicated') is not False
                or evidence.get('release_authorized') is not False
                or manifest.get('source_authenticity_verified') is not False
                or receipt.get('release_authorized') is not False
                or receipt.get('external_effects') is not False):
            raise ValueError('Evidex original-attachment execution failed its held-source receipt contract')
        attachment_refs = [register(evidex_attachment_evidence), register(evidex_attachment_receipt),
                           register(evidex_attachment_manifest), register(ROOT / 'scripts/run_evidex_attached_source_demo.py')]
        for item in files:
            attachment_refs.append(register(EVIDEX_ATTACHED_SOURCE_DEMO / item['path'], item['sha256']))
        run_groups['evidex_original_attachment_intake'] = {
            'source': register(evidex_attachment_evidence), 'route_receipt': register(evidex_attachment_receipt),
            'journey_count': 1, 'verified_journey_count': 1, 'refused_journey_count': 0,
            'original_file_count': len(files), 'all_original_file_hashes_verified': True,
            'boundary': 'Original customer-supplied text and CSV files are preserved and hash-bound; extracted statements remain unverified, and no support adjudication or release occurs.',
        }

    if HOMS_GRADE_EXAM_AUDIT.is_file():
        exam_audit = read_json(HOMS_GRADE_EXAM_AUDIT)
        if exam_audit.get('grade_count') != 12 or exam_audit.get('grades_1_through_12_present') is not True or exam_audit.get('all_grade_packs_verified') is not True:
            raise ValueError('HOMS randomized grade exam set failed the current content/hash audit')
        exam_ref = register(HOMS_GRADE_EXAM_AUDIT)
        print_pdfs = exam_audit.get('print_ready_pdfs') or {}
        if (print_pdfs.get('pdf_count') != 24 or print_pdfs.get('all_grade_pdfs_verified') is not True
                or print_pdfs.get('manifest') != HOMS_GRADE_EXAM_PDF_MANIFEST.relative_to(ROOT).as_posix()):
            raise ValueError('HOMS randomized exam set has incomplete print-ready PDF evidence')
        pdf_manifest = read_json(HOMS_GRADE_EXAM_PDF_MANIFEST)
        if pdf_manifest.get('grade_count') != 12 or pdf_manifest.get('pdf_count') != 24:
            raise ValueError('HOMS exam PDF manifest must bind two print files for each grade')
        register(HOMS_GRADE_EXAM_PDF_MANIFEST, print_pdfs.get('manifest_sha256'))
        for grade_row in pdf_manifest.get('grades') or []:
            for path_key, hash_key in (('exam_pdf', 'exam_pdf_sha256'), ('memo_pdf', 'memo_pdf_sha256')):
                register(HOMS_GRADE_EXAM_PDF_MANIFEST.parent / grade_row[path_key], grade_row.get(hash_key))
        pdf_bundle = ROOT / str(print_pdfs.get('bundle') or '')
        register(pdf_bundle, print_pdfs.get('bundle_sha256'))
        run_groups['homs_randomized_grade_exams'] = {
            'source': exam_ref, 'journey_count': 12, 'verified_journey_count': 12,
            'refused_journey_count': 0,
            'print_pdf_count': 24,
            'print_pdfs_verified': True,
            'boundary': exam_audit['caps_alignment_claim_boundary'] + ' Print-ready PDFs are bound to their editable DOCX sources and were checked for all question prompts and marking points.',
        }
        if HOMS_GRADE12_ACCURACY_REVISION.is_file():
            review = read_json(HOMS_GRADE12_ACCURACY_REVISION)
            if (review.get('grade') != 12 or review.get('subject') != 'Business Studies'
                    or review.get('classroom_release_authorized') is not False
                    or review.get('independent_moderation_decision') != 'NOT_ISSUED'):
                raise ValueError('HOMS Grade 12 accuracy revision evidence is missing its scope or release boundary')
            review_ref = register(HOMS_GRADE12_ACCURACY_REVISION)
            run_groups['homs_grade12_business_studies_accuracy_revision'] = {
                'source': review_ref, 'journey_count': 1, 'verified_journey_count': 1,
                'refused_journey_count': 0,
                'grade12_source_page': 38,
                'scope_disclosed': True,
                'boundary': review.get('professional_scope'),
            }
    if HOMS_QUESTION_CAPS_ALIGNMENT.is_file():
        alignment = read_json(HOMS_QUESTION_CAPS_ALIGNMENT)
        grades = alignment.get('grades', [])
        if (alignment.get('grade_count') != 12 or len(grades) != 12
                or alignment.get('all_exam_question_ids_mapped_exactly_once') is not True
                or alignment.get('all_cited_physical_pdf_pages_have_text') is not True
                or alignment.get('all_current_caps_source_hashes_verified') is not True
                or any(len(row.get('question_mappings', [])) != 5 for row in grades)):
            raise ValueError('HOMS question-level CAPS alignment map is incomplete or its source checks are not verified')
        alignment_ref = register(HOMS_QUESTION_CAPS_ALIGNMENT)
        run_groups['homs_question_level_caps_alignment'] = {
            'source': alignment_ref, 'journey_count': 12, 'verified_journey_count': 12,
            'refused_journey_count': 0,
            'mapped_question_count': sum(len(row['question_mappings']) for row in grades),
            'boundary': alignment.get('alignment_review_state'),
        }
    if HOMS_ACCREDITATION_CUSTOMER_EVIDENCE.is_file():
        accreditation = read_json(HOMS_ACCREDITATION_CUSTOMER_EVIDENCE)
        if accreditation.get('all_checks_pass') is not True or accreditation.get('checks', {}).get('criterion_stays_contested_with_two_open_gaps') is not True:
            raise ValueError('HOMS Accreditation customer evidence failed to retain its independent review gaps')
        accreditation_ref = register(HOMS_ACCREDITATION_CUSTOMER_EVIDENCE)
        for item in accreditation.get('artifacts', []):
            register(ROOT / item['path'], item['sha256'])
        run_groups['homs_accreditation_customer_packet'] = {
            'source': accreditation_ref, 'journey_count': 1, 'verified_journey_count': 1,
            'refused_journey_count': 0,
            'boundary': accreditation['claim_boundary'],
        }
    if HOMS_MODERATION_BATCH.is_file():
        moderation = read_json(HOMS_MODERATION_BATCH)
        if moderation.get('grade_count') != 12 or moderation.get('mechanical_pass_count') != 12 or moderation.get('independent_moderation_decision') != 'NOT_ISSUED':
            raise ValueError('HOMS Moderate batch is not twelve mechanical passes with independent decision withheld')
        moderation_ref = register(HOMS_MODERATION_BATCH)
        run_groups['homs_moderation_grade_batch'] = {
            'source': moderation_ref, 'journey_count': 12,
            'verified_journey_count': moderation['mechanical_pass_count'],
            'refused_journey_count': moderation['mechanical_correction_count'],
            'boundary': 'Mechanical HOMS Moderate checks passed; independent moderation decision is not issued and educator review remains required.',
        }
    if HOMS_MODERATE_COHORT_DEMO.is_dir():
        execution = read_json(HOMS_MODERATE_COHORT_DEMO / 'CUSTOMER_EXECUTION_RECEIPT.json')
        package = execution.get('receipt') or {}
        cohort = read_json(HOMS_MODERATE_COHORT_DEMO / 'HOMS_COHORT_ANALYSIS.json')
        inventory = {item['source_id']: item for item in package.get('source_inventory', [])}
        cohort_output = next((item for item in package.get('outputs', []) if item.get('path') == 'HOMS_COHORT_ANALYSIS.json'), {})
        cohort_path = HOMS_MODERATE_COHORT_DEMO / 'HOMS_COHORT_ANALYSIS.json'
        if (execution.get('requested_product') != 'HOMS Moderate'
                or package.get('status') != 'HELD_REVIEW_PACKAGE_RENDERED'
                or package.get('cohort_item_analysis', {}).get('human_review') != 'REQUIRED'
                or cohort.get('source_kind') != 'synthetic_fixture'
                or cohort.get('learner_level_scores_in_analysis_output') is not False
                or cohort.get('source_payload_retained_in_held_case') is not True
                or cohort.get('moderation_decision') != 'NOT_ISSUED'
                or cohort.get('release_authorized') is not False
                or cohort.get('record_count') != 8
                or cohort.get('source_sha256') != inventory.get('COHORT', {}).get('sha256')
                or cohort_output.get('sha256') != digest_file(cohort_path)
                or cohort_output.get('sha256') != package.get('cohort_item_analysis', {}).get('output_sha256')):
            raise ValueError('HOMS Moderate cohort analysis evidence is incomplete or exceeded its declared review boundary')
        demo_refs = []
        for path in (HOMS_MODERATE_COHORT_DEMO / 'CUSTOMER_EXECUTION_RECEIPT.json',
                     HOMS_MODERATE_COHORT_DEMO / 'CUSTOMER_PACKAGE_RECEIPT.json',
                     cohort_path,
                     HOMS_MODERATE_COHORT_DEMO / 'HOMS_MODERATION_FINDINGS.json',
                     HOMS_MODERATE_COHORT_DEMO / 'customer_delivery' / next(item['path'].split('/', 1)[1] for item in package['outputs'] if item['path'].endswith('.docx'))):
            demo_refs.append(register(path))
        run_groups['homs_moderate_cohort_item_analysis'] = {
            'source': demo_refs[0], 'report': demo_refs[2], 'journey_count': 1, 'verified_journey_count': 1,
            'refused_journey_count': 0,
            'boundary': 'Eight synthetic pseudonymous records exercise aggregate cohort distribution and item-to-rest statistics. No learner-level output, pass threshold, grade, approval, or release is produced.',
        }
    if HOMS_GRADE_CROSSWALKS.is_file():
        crosswalk_batch = read_json(HOMS_GRADE_CROSSWALKS)
        if crosswalk_batch.get('grade_count') != 12 or crosswalk_batch.get('all_grade_crosswalks_created') is not True:
            raise ValueError('HOMS grade learning crosswalk batch is incomplete')
        for grade_row in crosswalk_batch['grades']:
            for output in grade_row['crosswalk_files']:
                register(ROOT / output['path'], output['sha256'])
        crosswalk_ref = register(HOMS_GRADE_CROSSWALKS)
        run_groups['homs_grade_learning_crosswalks'] = {
            'source': crosswalk_ref, 'journey_count': 12, 'verified_journey_count': 12,
            'refused_journey_count': 0, 'boundary': crosswalk_batch['claim_boundary'],
        }
    if HOMS_ASSESS_GATE_FOLLOWUP.is_file():
        followup = read_json(HOMS_ASSESS_GATE_FOLLOWUP)
        route_result = ROOT / followup['source_route_result']
        route_receipt = ROOT / followup['batch_receipt']
        if digest_file(route_result) != followup['source_route_result_sha256'] or digest_file(route_receipt) != followup['batch_receipt_sha256']:
            raise ValueError('HOMS Assess follow-up route hashes changed after its feedback-gate review')
        followup_ref = register(HOMS_ASSESS_GATE_FOLLOWUP)
        register(route_result, followup['source_route_result_sha256'])
        register(route_receipt, followup['batch_receipt_sha256'])
        run_groups['homs_assess_feedback_gate_followup'] = {
            'source': followup_ref, 'journey_count': len(followup['learners']),
            'verified_journey_count': sum(row['exact_source_quotes_present'] for row in followup['learners']),
            'refused_journey_count': 0,
            'boundary': followup['score_stability'] + ' ' + followup['unit_gate_regression_observation'],
        }
    if HOMS_ASSESS_SCORE_STABILITY.is_file():
        stability = read_json(HOMS_ASSESS_SCORE_STABILITY)
        if stability.get('score_stability') != 'FIXED_CONFIGURATION_REPEAT_STABLE; CROSS_TEMPERATURE_VARIANCE_REMAINS; CONTRADICTORY_FEEDBACK_HELD' or len(stability.get('runs', [])) != 5:
            raise ValueError('HOMS Assess score-stability experiment is missing its repeated configuration evidence')
        stability_ref = register(HOMS_ASSESS_SCORE_STABILITY)
        for run in stability['runs']:
            register(ROOT / run['results_path'], run['results_sha256'])
        run_groups['homs_assess_score_stability'] = {
            'source': stability_ref, 'journey_count': 10, 'verified_journey_count': 10,
            'refused_journey_count': 0,
            'boundary': 'Temperature 0.0 repeats matched for this model/input; temperature 0.3 scores varied. Three contradictions persist but draft feedback is now replaced by review instructions, with original model text preserved. Marks remain provisional.',
        }
    if HOMS_ASSESS_SCORE_WITHHOLDING.is_file():
        withholding = read_json(HOMS_ASSESS_SCORE_WITHHOLDING)
        if withholding.get('all_checks_pass') is not True or withholding.get('execution', {}).get('flagged_score_count') < 1:
            raise ValueError('HOMS Assess score-withholding evidence did not verify a held flagged score')
        withholding_ref = register(HOMS_ASSESS_SCORE_WITHHOLDING)
        for item in withholding.get('artifacts', []):
            register(ROOT / item['path'], item['sha256'])
        run_groups['homs_assess_flagged_score_withholding'] = {
            'source': withholding_ref, 'journey_count': withholding['execution']['learner_count'],
            'verified_journey_count': withholding['execution']['learner_count'],
            'refused_journey_count': withholding['execution']['flagged_score_count'],
            'boundary': withholding['claim_boundary'],
        }
    if DOCUMENT_STUDIO_LOCALIZE_FOLLOWUP.is_file():
        localize = read_json(DOCUMENT_STUDIO_LOCALIZE_FOLLOWUP)
        if len(localize.get('current_automated_errors', [])) != 1 or localize.get('current_release_authorized') is not False:
            raise ValueError('Document Studio Localize follow-up did not preserve its single blocking language error and held release')
        localize_ref = register(DOCUMENT_STUDIO_LOCALIZE_FOLLOWUP)
        for output in localize['outputs']:
            register(ROOT / output['path'], output['sha256'])
        for experiment in localize.get('critic_experiments', []):
            for output in experiment['outputs']:
                register(ROOT / output['path'], output['sha256'])
        run_groups['document_studio_localize_advisory_terminology_followup'] = {
            'source': localize_ref, 'journey_count': 8, 'verified_journey_count': 7,
            'refused_journey_count': 1,
            'boundary': 'Unapproved glossary phrases are advisory; the paired English source term is allowed. P6 negation remains blocking. An opt-in critic hallucinated from a short heading, and the source-expansion guard now rejects it. Human language review and release remain blocked.',
        }
    if FULL_PORTFOLIO_REPORT.is_file():
        full_portfolio = read_json(FULL_PORTFOLIO_REPORT)
        canonical_ref = Path(full_portfolio['canonical_53']['receipt'])
        supplemental_ref = Path(full_portfolio['supplemental_15']['report'])
        canonical_path = ROOT / canonical_ref
        supplemental_path = ROOT / supplemental_ref
        if digest_file(canonical_path) != full_portfolio['canonical_53']['receipt_sha256']:
            raise ValueError('current canonical portfolio receipt hash changed after its 68-product evidence report')
        if digest_file(supplemental_path) != full_portfolio['supplemental_15']['report_sha256']:
            raise ValueError('current supplemental evidence hash changed after its 68-product evidence report')
        canonical = read_json(canonical_path)
        supplemental = read_json(supplemental_path)
        canonical_names = {row['incarnation'] for row in canonical['results']
                           if row['status'] == 'PASS_FULL_PIPELINE'}
        supplemental_names = {row['product_name'] for row in supplemental['products']
                              if row['status'] == 'PASS_FULL_PIPELINE'
                              and row['artifacts_all_match'] and row['source_bindings_all_match']}
        expected_names = set(full_portfolio['products'])
        if (len(canonical_names) != 53 or len(supplemental_names) != 15
                or canonical_names & supplemental_names
                or canonical_names | supplemental_names != expected_names
                or len(expected_names) != 68):
            raise ValueError('current 68-product full-pipeline evidence does not cover the catalog exactly once')
        register(FULL_PORTFOLIO_REPORT)
        register(canonical_path, declared_sha256=full_portfolio['canonical_53']['receipt_sha256'])
        register(supplemental_path, declared_sha256=full_portfolio['supplemental_15']['report_sha256'])
        full_by_offer = {
            **{name: {'status': 'PASS_FULL_PIPELINE', 'evidence_group': 'current_68_product_full_pipeline',
                      'receipt': str(canonical_ref), 'executor_rematerialized_packet': False}
               for name in canonical_names},
            **{name: {'status': 'PASS_FULL_PIPELINE', 'evidence_group': 'current_68_product_full_pipeline',
                      'receipt': str(supplemental_ref), 'executor_rematerialized_packet': False}
               for name in supplemental_names},
        }
        run_groups['current_68_product_full_pipeline'] = {
            'source': register(FULL_PORTFOLIO_REPORT),
            'generated_at': full_portfolio['created_at_utc'],
            'journey_count': 68, 'verified_journey_count': 68, 'refused_journey_count': 0,
            'boundary': full_portfolio['claim_boundary'],
        }
        # HOMS Assess is the focused unresolved HOMS quality path. Keep its
        # current receipt and model-instability evidence attached explicitly.
        if HOMS_ASSESS_QUALITY_REPORT.is_file():
            register(HOMS_ASSESS_QUALITY_REPORT)

    seraph_ai_batch = None
    if SERAPH_TELEMETRY_AI_PROFILE_BATCH.is_dir():
        batch_path = SERAPH_TELEMETRY_AI_PROFILE_BATCH / 'BATCH_RECEIPT.json'
        seraph_ai_batch = read_json(batch_path)
        results = seraph_ai_batch.get('results') or []
        expected = {'AI IncidentRoom', 'AssuranceRoom', 'CriticalAI Assurance', 'CyberAssurance',
                    'ControlDrift', 'DORA Vendor Assurance', 'ModelProof', 'ReleaseProof',
                    'DIO AI Assurance', 'Agent Authority', 'ChangeProof'}
        if ({row.get('product_name') for row in results} != expected
                or any(row.get('status') != 'EXECUTED_AND_BOUND' for row in results)
                or seraph_ai_batch.get('all_review_boundaries_preserved') is not True
                or seraph_ai_batch.get('product_qualification') != 'NOT_ESTABLISHED'):
            raise ValueError('Seraph AI-profile batch is incomplete or crossed its review boundary')
        run_groups['seraph_telemetry_ai_profiles'] = {
            'source': register(batch_path), 'journey_count': len(results),
            'verified_journey_count': len(results), 'refused_journey_count': 0,
            'boundary': 'Case-bound hash-chain review for opt-in telemetry; unsigned/missing/scope-mismatched telemetry remains challenged, and source trust and release authority remain unestablished.',
        }
        for result in results:
            case_dir = SERAPH_TELEMETRY_AI_PROFILE_BATCH / str(result['case_output_dir'])
            for row in result.get('files') or []:
                path = case_dir / row['path']
                register(path, row.get('sha256'))

    capabilities = {}
    for key, config in CAPABILITIES.items():
        files = capability_files(key, config)
        refs = [register(path) for path in files]
        customer_surfaces = [str(path.relative_to(ROOT)) for path in files
                             if path.suffix.lower() in {'.pdf', '.docx', '.pptx', '.xlsx'}
                             and ('customer_delivery' in path.parts or 'report' in path.parts
                                  or 'pitch' in path.parts or 'article' in path.parts)]
        if key == 'launch_kit_preparation':
            customer_surfaces = [str(path.relative_to(ROOT)) for path in files
                                 if path.name == 'landing.html' or path.suffix.lower() == '.png' and 'assets' in path.parts]
        if not customer_surfaces:
            raise ValueError(f'no actual customer surface for pilot capability: {key}')
        capabilities[key] = {**config, 'assessment': 'OPERATOR_ASSESSED_BOUNDED_PAID_PILOT_CANDIDATE',
                             'example_context': 'Controlled/synthetic examples, not independent customer acceptance.',
                             'artifact_refs': refs, 'customer_deliverable_refs': customer_surfaces,
                             'independent_professional_signoff': False, 'commercial_validation': 'UNPROVED'}

    rows = []
    for catalog_row in sorted(catalog, key=lambda row: row['product_name']):
        name = catalog_row['product_name']
        old = historical[name]
        # Keep original findings, statuses and timestamps verbatim. Current
        # observations are an overlay, never a rewrite of the baseline audit.
        historical_refs = [register(ROOT / value['path'], value.get('sha256')) for value in old.get('artifacts', [])]
        current = fresh_by_offer.get(name)
        current_full = full_by_offer.get(name)
        key = pilot_map.get(name)
        limits = [str(old.get('known_capability_limits') or 'Historical quality limits remain applicable until specifically superseded.')]
        disposition = 'HISTORICAL_ASSESSMENT_RETAINED_NOT_FRESHLY_RERUN'
        changes = []
        product_specific_refs = []
        specialist_qualification_receipt = None
        specialist_qualification_root = None
        site_studio_accessibility = None
        if name == 'Site Studio' and SITE_STUDIO_ACCESSIBILITY_RUN.is_dir():
            site_case = SITE_STUDIO_ACCESSIBILITY_RUN / 'site-studio/site-studio'
            site_root = site_case / 'EXECUTION/site_draft'
            evidence_path = OUTPUT / 'SITE_STUDIO_ACCESSIBILITY_EVIDENCE_20261102.json'
            route_receipt_path = site_case / 'PROFESSIONAL_EVIDENCE_RECEIPT.json'
            proof_path = site_root / 'PROOF_MANIFEST.json'
            required = [evidence_path, route_receipt_path, proof_path,
                        site_root / 'marketfront/index.html', site_root / 'marketfront/styles.css',
                        site_root / 'marketfront/app.js', site_root / 'strategy/SITE_COMPOSITION_PLAN.json']
            if not all(path.is_file() for path in required):
                raise ValueError('Site Studio accessibility customer route is missing a required artifact')
            site_studio_accessibility = read_json(evidence_path)
            site_route = read_json(route_receipt_path)
            site_proof = read_json(proof_path)
            site_html = site_root / 'marketfront/index.html'
            site_css = site_root / 'marketfront/styles.css'
            site_js = site_root / 'marketfront/app.js'
            if (site_studio_accessibility.get('schema') != 'dio.site_studio.accessibility_and_source_render_review.v1'
                    or not all((site_studio_accessibility.get('checks') or {}).values())
                    or site_studio_accessibility.get('index_html_sha256') != digest_file(site_html)
                    or site_studio_accessibility.get('stylesheet_sha256') != digest_file(site_css)
                    or site_studio_accessibility.get('script_sha256') != digest_file(site_js)
                    or site_studio_accessibility.get('route_receipt_sha256') != digest_file(route_receipt_path)
                    or site_route.get('status') != 'PASS_FULL_PIPELINE'
                    or site_route.get('human_review_required') is not True
                    or site_route.get('external_publication') != 'REFUSE'
                    or site_route.get('authority_created') is not False
                    or site_proof.get('external_publication') != 'REFUSE'
                    or site_proof.get('external_effects') is not False):
                raise ValueError('Site Studio accessibility/source review is stale or crosses its held boundary')
            for required_artifact in required:
                product_specific_refs.append(register(required_artifact))
            changes.append('The earlier Site Studio sample preserved source-bound copy, keyboard navigation, and draft-only publication controls. It exposed a product-level issue: the page still showed internal builder branding and intake controls rather than a customer website.')
            limits.append('The accessibility review covers generated HTML/CSS structure and source-copy rendering; it is not a WCAG conformance audit, human usability test or publication approval.')
            disposition = 'CURRENT_HELD_EXECUTION_VERIFIED'
        if name == 'Site Studio' and SITE_STUDIO_PROFESSIONAL_DRAFT_RUN.is_dir():
            site_run = SITE_STUDIO_PROFESSIONAL_DRAFT_RUN
            site_root = site_run / 'EXECUTION/site_draft'
            site_html = site_root / 'marketfront/index.html'
            site_css = site_root / 'marketfront/styles.css'
            review_notes = site_root / 'site-review/CUSTOMER_REVIEW_NOTES.md'
            plan_path = site_root / 'strategy/SITE_COMPOSITION_PLAN.json'
            source_manifest_path = site_run / 'PROJECTION/SITE_STUDIO_MANIFEST.json'
            proof_path = site_root / 'PROOF_MANIFEST.json'
            native_receipt_path = site_run / 'NATIVE_CUSTOMER_PACKET_RECEIPT.json'
            delivery_receipt_path = site_run / 'CUSTOMER_SITE_DRAFT_DELIVERY_RECEIPT.json'
            browser_review_path = site_run / 'RENDERED_REVIEW_EVIDENCE.json'
            bundle_path = site_run / 'CUSTOMER_SITE_DRAFT_PACKAGE.zip'
            required_site_paths = [site_html, site_css, review_notes, plan_path, source_manifest_path, proof_path,
                                   native_receipt_path, delivery_receipt_path, browser_review_path,
                                   bundle_path, site_run / 'CUSTOMER_SITE_PREVIEW_README.md',
                                   site_run / 'OWNER_REVIEW_NOTES.md']
            if not all(path.is_file() for path in required_site_paths):
                raise ValueError('Site Studio professional draft package is incomplete')
            site_html_text = site_html.read_text(encoding='utf-8')
            review_notes_text = review_notes.read_text(encoding='utf-8')
            site_plan = read_json(plan_path)
            site_proof = read_json(proof_path)
            native_site = read_json(native_receipt_path)
            delivery = read_json(delivery_receipt_path)
            browser_review = read_json(browser_review_path)
            browser_rows = browser_review.get('viewports') or []
            expected_source_records = site_plan.get('customer_content_source_bindings') or []
            expected_service_titles = ['Research strategy', 'Evidence synthesis', 'Decision communication']
            proof_artifacts = {row['path']: row.get('sha256') for row in site_proof.get('artifacts', [])}
            bundle_members = {}
            with zipfile.ZipFile(bundle_path) as bundle:
                for info in bundle.infolist():
                    if info.is_dir():
                        continue
                    bundle_members[info.filename] = hashlib.sha256(bundle.read(info.filename)).hexdigest()
            delivery_by_path = {row.get('path'): row.get('sha256') for row in delivery.get('website_artifacts', [])}
            source_records_bound = bool(expected_source_records) and all(
                row.get('source_text') and row['source_text'] in review_notes_text
                for row in expected_source_records
            )
            browser_shape_ok = (
                len(browser_rows) == 2
                and {row.get('viewport_width') for row in browser_rows} == {390, 1440}
                and all(row.get('document_width') == row.get('viewport_width')
                        and row.get('body_width') == row.get('viewport_width')
                        and row.get('h1') == 1 and row.get('forms') == 0 and row.get('scripts') == 0
                        for row in browser_rows)
            )
            if (native_site.get('terminal_artifact_kind') != 'static_website_draft_pack'
                    or native_site.get('route') != 'site_studio_raw_composition'
                    or native_site.get('native_receipt', {}).get('controlled_artifact_generation') != 'PASS'
                    or native_site.get('native_receipt', {}).get('external_publication') != 'REFUSE'
                    or native_site.get('native_receipt', {}).get('authority_created') is not False
                    or site_proof.get('external_publication') != 'REFUSE'
                    or site_proof.get('external_effects') is not False
                    or site_proof.get('manifest_sha256') != digest_file(source_manifest_path)
                    or 'Karoo Research Advisory' not in site_html_text
                    or 'DIO // SITE STUDIO' in site_html_text
                    or 'CONTROLLED COMPOSITION PROOF' in site_html_text
                    or 'site-intake' in site_html_text
                    or not all(title in site_html_text for title in expected_service_titles)
                    or not source_records_bound
                    or not browser_shape_ok
                    or browser_review.get('source_html_sha256') != digest_file(site_html)
                    or browser_review.get('stylesheet_sha256') != digest_file(site_css)
                    or delivery.get('packet_fingerprint') != native_site.get('packet_fingerprint')
                    or delivery.get('studio_proof_fingerprint') != site_proof.get('proof_fingerprint')
                    or delivery.get('external_publication') != 'REFUSE'
                    or delivery.get('external_effects') is not False
                    or delivery.get('contact_route_state') != 'NOT_SUPPLIED_NOT_INVENTED'
                    or delivery.get('archive', {}).get('sha256') != digest_file(bundle_path)
                    or delivery.get('archive', {}).get('bytes') != bundle_path.stat().st_size
                    or delivery_by_path.get('marketfront/index.html') != digest_file(site_html)
                    or delivery_by_path.get('marketfront/styles.css') != digest_file(site_css)
                    or bundle_members.get('marketfront/index.html') != digest_file(site_html)
                    or bundle_members.get('marketfront/styles.css') != digest_file(site_css)
                    or bundle_members.get('OWNER_REVIEW_NOTES.md') != digest_file(site_run / 'OWNER_REVIEW_NOTES.md')
                    or proof_artifacts.get('marketfront/index.html') != digest_file(site_html)
                    or proof_artifacts.get('marketfront/styles.css') != digest_file(site_css)
                    or proof_artifacts.get('site-review/CUSTOMER_REVIEW_NOTES.md') != digest_file(review_notes)):
                raise ValueError('Site Studio professional customer draft failed copy/source, browser, bundle, or authority checks')
            for required_site_path in required_site_paths:
                product_specific_refs.append(register(required_site_path))
            for implementation_path in (ROOT / 'products/studio_harvest.py',
                                        ROOT / 'products/professional_evidence_execution.py',
                                        ROOT / 'products/native_customer_runner.py'):
                product_specific_refs.append(register(implementation_path))
            for screenshot in (site_run / 'RENDERED_REVIEW').glob('*.png'):
                product_specific_refs.append(register(screenshot))
            changes.append('The current Site Studio run now produces a client-branded, responsive static website, with the customer’s three service descriptions and no internal DIO builder labels or false contact form. A separate owner-review note binds all seven source statements and marks missing contact details as a publication decision. Chromium review at 390 and 1440 pixels found no horizontal overflow; the customer preview bundle stays offline and unpublished.')
            limits.append('The preview still needs owner approval of brand and service copy, supplied contact details, and a release owner. The bounded visual review is not a WCAG conformance audit, accessibility usability test, or deployment approval.')
            disposition = 'CURRENT_HELD_EXECUTION_VERIFIED'
        offer_lab_source_review = None
        if name == 'Offer Lab' and OFFER_LAB_SOURCE_REVIEW_RUN.is_dir():
            offer_case = OFFER_LAB_SOURCE_REVIEW_RUN / 'offer-lab/offer-lab'
            offer_exec = offer_case / 'EXECUTION'
            offer_path = offer_exec / 'BOUNDED_OFFER.json'
            offer_receipt_path = offer_exec / 'OFFER_LAB_RECEIPT.json'
            worksheet_path = offer_exec / 'OFFER_REVIEW_WORKSHEET.csv'
            review_page_path = offer_exec / 'OFFER_REVIEW.html'
            review_tool_path = offer_exec / 'OFFER_REVIEW_VALIDATOR.py'
            review_validation_path = offer_exec / 'OFFER_REVIEW_VALIDATION.json'
            professional_receipt_path = offer_case / 'PROFESSIONAL_EVIDENCE_RECEIPT.json'
            register_path = offer_case / 'CUSTOMER_PACKET/SOURCES/02_evidence_register.csv'
            required = [offer_path, offer_receipt_path, worksheet_path, review_page_path, review_tool_path,
                        review_validation_path, professional_receipt_path, register_path]
            if not all(path.is_file() for path in required):
                raise ValueError('Offer Lab source review route is missing a required artifact')
            offer_lab_source_review = read_json(offer_path)
            offer_receipt = read_json(offer_receipt_path)
            offer_review_validation = read_json(review_validation_path)
            professional_receipt = read_json(professional_receipt_path)
            source_bytes = register_path.read_bytes()
            register_sha = hashlib.sha256(source_bytes).hexdigest()
            with worksheet_path.open(encoding='utf-8-sig', newline='') as handle:
                worksheet_rows = list(csv.DictReader(handle))
            source_records = offer_lab_source_review.get('source_records') or []
            exact_source_rows = []
            for source_row in source_records:
                start, end = source_row.get('source_byte_start'), source_row.get('source_byte_end_exclusive')
                statement = str(source_row.get('statement') or '')
                span = source_bytes[start:end] if isinstance(start, int) and isinstance(end, int) and 0 <= start < end <= len(source_bytes) else b''
                exact_source_rows.append(bool(span) and source_row.get('source_register_sha256') == register_sha
                    and hashlib.sha256(span).hexdigest() == source_row.get('source_row_sha256')
                    and hashlib.sha256(statement.encode('utf-8')).hexdigest() == source_row.get('source_statement_sha256')
                    and statement.encode('utf-8') in span)
            declared = {row.get('path'): row.get('sha256') for row in offer_receipt.get('artifacts') or []}
            if (offer_lab_source_review.get('schema') != 'dio.offer_lab.professional_offer.v1'
                    or len(source_records) < 3 or len(worksheet_rows) != len(source_records)
                    or not exact_source_rows or not all(exact_source_rows)
                    or any(row.get('customer_statement') != source_records[index].get('statement')
                           or not row.get('source_ref') or not row.get('source_byte_ref')
                           for index, row in enumerate(worksheet_rows))
                    or not worksheet_rows or 'reviewer_role' not in worksheet_rows[0]
                    or any(row.get('reviewer_decision') or row.get('reviewer_name') or row.get('rationale') for row in worksheet_rows)
                    or offer_review_validation.get('validation_state') != 'REVIEW_INCOMPLETE_OR_HOLD_REQUIRED'
                    or offer_review_validation.get('review_row_count') != len(source_records)
                    or offer_review_validation.get('reviewer_decision_count') != 0
                    or offer_review_validation.get('all_source_rows_verified') is not True
                    or offer_review_validation.get('external_release') != 'REFUSE'
                    or offer_review_validation.get('authority_created') is not False
                    or any(declared.get(path.name) != digest_file(path) for path in (offer_path, worksheet_path, review_page_path, review_tool_path, review_validation_path))
                    or professional_receipt.get('status') != 'PASS_FULL_PIPELINE'
                    or professional_receipt.get('external_effects') is not False
                    or professional_receipt.get('authority_created') is not False
                    or offer_lab_source_review.get('market_demand_claimed') is not False
                    or offer_lab_source_review.get('willingness_to_pay_proved') is not False
                    or offer_lab_source_review.get('external_release') != 'REFUSE'):
                raise ValueError('Offer Lab review worksheet is stale, source-unbound, or crosses its claim boundary')
            for required_artifact in required:
                product_specific_refs.append(register(required_artifact))
            product_specific_refs.append(register(ROOT / 'products/professional_evidence_native.py'))
            product_specific_refs.append(register(ROOT / 'products/offer_lab_review.py'))
            product_specific_refs.append(register(review_validation_path))
            changes.append(f'Offer Lab now byte-binds all {len(source_records)} customer-declared offer inputs to their exact evidence-register rows and provides an offline decision/rationale worksheet for each component. Reviewer fields start blank; demand, willingness to pay, and release remain unproved/refused.')
            changes.append('The Offer Lab review export now carries each exact customer statement and its source locator/byte reference into the downloaded worksheet. The qualification builder checks those exported fields against the source-bound offer records.')
            changes.append('Offer Lab now requires a decision, reviewer name and role, timezone-aware review time, and rationale for every component before browser export. Its offline validator rechecks the customer register bytes and review values while keeping demand, professional suitability, and release unproven.')
            limits.append('The offer remains a customer hypothesis. The review surface records owner input only and does not validate market demand, price, payment, or professional suitability.')
            disposition = 'CURRENT_HELD_EXECUTION_VERIFIED'
        dossierops_review_surface = None
        if name == 'DossierOps' and DOSSIEROPS_REVIEW_SURFACE_ROUTE.is_dir():
            dossier_case = DOSSIEROPS_REVIEW_SURFACE_ROUTE / 'dossierops/dossierops'
            dossier_exec = dossier_case / 'EXECUTION'
            route_receipt_path = dossier_case / 'PROFESSIONAL_EVIDENCE_RECEIPT.json'
            processing_receipt_path = dossier_exec / 'DOSSIEROPS_PROCESSING_RECEIPT.json'
            bundle_manifest_path = dossier_exec / 'DOSSIER_BUNDLE_MANIFEST.json'
            proof_path = dossier_exec / 'PROOF_MANIFEST.json'
            index_path = dossier_exec / 'DOSSIEROPS_DOSSIER_INDEX.json'
            index_html_path = dossier_exec / 'DOSSIEROPS_DOSSIER_INDEX.html'
            bundle_path = dossier_exec / 'DOSSIEROPS_CONTROLLED_DOSSIER.zip'
            studio_receipt_path = dossier_case / 'DOSSIER_PROJECTION/document_studio/PRO-DOSSIEROPS-DOC/DOCUMENT_STUDIO_RECEIPT.json'
            required = [route_receipt_path, processing_receipt_path, bundle_manifest_path, proof_path,
                        index_path, index_html_path, bundle_path, studio_receipt_path]
            if not all(path.is_file() for path in required):
                raise ValueError('DossierOps reviewer surface route is missing a required artifact')
            route_receipt = read_json(route_receipt_path)
            processing_receipt = read_json(processing_receipt_path)
            bundle_manifest = read_json(bundle_manifest_path)
            proof = read_json(proof_path)
            dossier_index = read_json(index_path)
            studio_receipt = read_json(studio_receipt_path)
            manifest_members = bundle_manifest.get('members') or []
            archive_members_ok = False
            try:
                with zipfile.ZipFile(bundle_path) as archive:
                    archive_names = set(archive.namelist())
                    manifest_archive_name = processing_receipt.get('bundle_manifest', {}).get('filename')
                    expected_archive_names = {row.get('path') for row in manifest_members} | {manifest_archive_name}
                    archive_members_ok = archive_names == expected_archive_names
                    for member in manifest_members:
                        if not archive_members_ok:
                            break
                    if archive_members_ok:
                        archive_members_ok = archive.read(manifest_archive_name) == bundle_manifest_path.read_bytes()
                        data = archive.read(member['path'])
                        archive_members_ok = (len(data) == member.get('bytes')
                                              and hashlib.sha256(data).hexdigest() == member.get('sha256'))
                        if not archive_members_ok:
                            break
            except (OSError, zipfile.BadZipFile, KeyError):
                archive_members_ok = False
            route_artifacts = {row.get('path'): row.get('sha256') for row in route_receipt.get('artifacts') or []}
            proof_index_html = next((row for row in proof.get('artifacts') or []
                                     if row.get('artifact_type') == 'DOSSIER_INDEX_HTML'), {})
            worksheet_controls = all(token in index_html_path.read_text(encoding='utf-8') for token in (
                'id=\'filter\'', 'data-field=\'reviewer_decision\'', 'data-field=\'reviewer_name\'',
                'data-field=\'rationale\'', 'DOSSIEROPS_REVIEW_WORKSHEET.csv', 'role=\'status\''))
            if (route_receipt.get('status') != 'PASS_FULL_PIPELINE'
                    or route_receipt.get('human_review_required') is not True
                    or route_receipt.get('external_publication') != 'REFUSE'
                    or route_receipt.get('authority_created') is not False
                    or route_receipt.get('external_effects') is not False
                    or processing_receipt.get('internal_processing') != 'COMPLETE'
                    or processing_receipt.get('human_review_gate') != 'NEEDS_YOU'
                    or processing_receipt.get('external_release_gate') != 'REFUSE'
                    or processing_receipt.get('external_effects') is not False
                    or any((processing_receipt.get('forbidden_outcomes_created') or {}).values())
                    or bundle_manifest.get('schema') != 'dio.dossier_assembly.bundle_manifest.v1'
                    or bundle_manifest.get('member_count') != len(manifest_members)
                    or bundle_manifest.get('bound_proof_fingerprint') != proof.get('proof_fingerprint')
                    or not archive_members_ok
                    or proof_index_html.get('sha256') != digest_file(index_html_path)
                    or processing_receipt.get('bundle', {}).get('sha256') != digest_file(bundle_path)
                    or processing_receipt.get('bundle_manifest', {}).get('sha256') != digest_file(bundle_manifest_path)
                    or route_artifacts.get('EXECUTION/DOSSIEROPS_DOSSIER_INDEX.html') != digest_file(index_html_path)
                    or route_artifacts.get('EXECUTION/DOSSIEROPS_CONTROLLED_DOSSIER.zip') != digest_file(bundle_path)
                    or studio_receipt.get('processing', {}).get('remote_inference_used') is not False
                    or studio_receipt.get('release', {}).get('human_approval_required') is not True
                    or not worksheet_controls):
                raise ValueError('DossierOps review surface, bundle integrity, local-processing claim, or held boundary failed')
            dossierops_review_surface = dossier_index
            for required_artifact in required:
                product_specific_refs.append(register(required_artifact))
            changes.append(f'DossierOps now presents {len(dossier_index.get("items") or [])} hash-bound records with direct file links, filtering, and a local reviewer worksheet export. The extracted bundle manifest was checked against every ZIP member; release remains refused and legal/completeness conclusions remain unissued.')
            limits.append('The review worksheet records reviewer input but does not change source evidence or grant release. Authenticity, completeness, sufficiency, legal effect and final delivery require separate human decisions.')
            disposition = 'CURRENT_HELD_EXECUTION_VERIFIED'
        vesper_source_review = None
        if name == 'Vesper Desk' and VESPER_DESK_SOURCE_REVIEW_RUN.is_dir():
            vesper_case = VESPER_DESK_SOURCE_REVIEW_RUN / 'vesper-desk/vesper-desk'
            vesper_exec = vesper_case / 'EXECUTION'
            bindings_path = vesper_exec / 'VESPER_SOURCE_BINDINGS.json'
            receipt_path = vesper_exec / 'VESPER_RECEIPT.json'
            worksheet_path = vesper_exec / 'VESPER_REVIEW_WORKSHEET.csv'
            review_path = vesper_exec / 'VESPER_REVIEW.html'
            draft_path = vesper_exec / 'VESPER_DRAFT_NEXT_STEP.md'
            route_receipt_path = vesper_case / 'PROFESSIONAL_EVIDENCE_RECEIPT.json'
            intake_path = vesper_case / 'CUSTOMER_PACKET/INTAKE.json'
            register_path = vesper_case / 'CUSTOMER_PACKET/SOURCES/02_evidence_register.csv'
            email_path = vesper_case / 'CUSTOMER_PACKET/SOURCES/intake_email.json'
            required = [bindings_path, receipt_path, worksheet_path, review_path, draft_path,
                        route_receipt_path, intake_path, register_path]
            if not all(path.is_file() for path in required):
                raise ValueError('Vesper Desk source review route is missing a required artifact')
            vesper_source_review = read_json(bindings_path)
            vesper_receipt = read_json(receipt_path)
            route_receipt = read_json(route_receipt_path)
            bindings = vesper_source_review.get('bindings') or []
            with worksheet_path.open(encoding='utf-8-sig', newline='') as handle:
                review_rows = list(csv.DictReader(handle))
            intake_bytes = intake_path.read_bytes()
            register_bytes = register_path.read_bytes()
            intake_doc = json.loads(intake_bytes.decode('utf-8'))
            exact_bindings = []
            for binding in bindings:
                source_id = binding.get('source_id')
                if source_id == 'INTAKE.json':
                    source_bytes = intake_bytes
                elif source_id == '02_evidence_register.csv':
                    source_bytes = register_bytes
                elif source_id == 'intake_email.json' and email_path.is_file():
                    source_bytes = email_path.read_bytes()
                else:
                    source_bytes = b''
                start, end = binding.get('source_byte_start'), binding.get('source_byte_end_exclusive')
                span = source_bytes[start:end] if isinstance(start, int) and isinstance(end, int) and 0 <= start < end <= len(source_bytes) else b''
                value = str(binding.get('value') or '')
                exact_bindings.append(bool(span)
                    and hashlib.sha256(source_bytes).hexdigest() == binding.get('source_file_sha256')
                    and hashlib.sha256(span).hexdigest() == binding.get('source_row_sha256')
                    and hashlib.sha256(value.encode('utf-8')).hexdigest() == binding.get('source_statement_sha256')
                    and value.encode('utf-8') in span)
            artifact_hashes = {row.get('path'): row.get('sha256') for row in vesper_receipt.get('artifacts') or []}
            artifact_paths = [draft_path, bindings_path, worksheet_path, review_path]
            if (vesper_source_review.get('schema') != 'dio.vesper.customer_intake_source_bindings.v1'
                    or vesper_source_review.get('intake_email_file_supplied') is not email_path.is_file()
                    or (not email_path.is_file() and any(row.get('source_id') == 'intake_email.json' for row in bindings))
                    or vesper_source_review.get('packet_intake_source_sha256') != hashlib.sha256(intake_bytes).hexdigest()
                    or vesper_source_review.get('evidence_register_source_sha256') != hashlib.sha256(register_bytes).hexdigest()
                    or not any(row.get('source_id') == 'INTAKE.json' and row.get('source_field') == 'request'
                               and row.get('value') == str(intake_doc.get('request') or '') for row in bindings)
                    or len(bindings) != len(review_rows) or not exact_bindings or not all(exact_bindings)
                    or any(row.get('reviewer_decision') or row.get('reviewer_name') or row.get('rationale')
                           or row.get('revised_value') for row in review_rows)
                    or any(artifact_hashes.get(path.name) != digest_file(path) for path in artifact_paths)
                    or vesper_receipt.get('human_review_state') != 'PENDING_HUMAN_REVIEW'
                    or vesper_receipt.get('external_send') != 'REFUSE'
                    or vesper_receipt.get('authority_created') is not False
                    or vesper_receipt.get('external_effects') is not False
                    or vesper_receipt.get('attachments_content_read') is not False
                    or route_receipt.get('status') != 'PASS_FULL_PIPELINE'
                    or route_receipt.get('external_send') != 'REFUSE'
                    or route_receipt.get('authority_created') is not False
                    or route_receipt.get('external_effects') is not False):
                raise ValueError('Vesper Desk source review is stale, unbound, or crossed its human-review boundary')
            for required_artifact in required:
                product_specific_refs.append(register(required_artifact))
            product_specific_refs.extend(register(ROOT / path) for path in [
                'products/professional_evidence_execution.py', 'scripts/build_customer_product_qualification.py'])
            changes.append(f'Vesper Desk now provides an offline intake review worksheet for {len(bindings)} source-bound values. The absent email file is recorded as absent; the fallback request and evidence-register rows are byte-anchored. Routing remains a suggestion, attachment contents are unread, and human approval is pending.')
            limits.append('Source hashes establish which supplied text informed routing; they do not verify sender identity, truth, urgency, attachment contents or authorization. No reply is sent.')
            disposition = 'CURRENT_HELD_EXECUTION_VERIFIED'
        opportunity_foundry_review = None
        if name == 'Opportunity Foundry' and OPPORTUNITY_FOUNDRY_REVIEW_ROUTE.is_dir():
            opportunity_case = OPPORTUNITY_FOUNDRY_REVIEW_ROUTE / 'opportunity-foundry'
            opportunity_exec = opportunity_case / 'EXECUTION'
            native_receipt_path = opportunity_case / 'NATIVE_CUSTOMER_PACKET_RECEIPT.json'
            result_path = opportunity_exec / 'RANKED_OPPORTUNITY_HYPOTHESES.json'
            review_path = opportunity_exec / 'OPPORTUNITY_FOUNDRY_REVIEW.html'
            brief_path = opportunity_exec / 'OPPORTUNITY_FOUNDRY_BRIEF.md'
            output_receipt_path = opportunity_exec / 'OPPORTUNITY_FOUNDRY_RECEIPT.json'
            register_path = opportunity_case / 'CUSTOMER_PACKET/SOURCES/02_evidence_register.csv'
            required = [native_receipt_path, result_path, review_path,
                        brief_path, output_receipt_path, register_path]
            if not all(path.is_file() for path in required):
                raise ValueError('Opportunity Foundry customer review route is missing a required artifact')
            native_receipt = read_json(native_receipt_path)
            route_receipt = native_receipt
            output_receipt = read_json(output_receipt_path)
            opportunity_foundry_review = read_json(result_path)
            source_bytes = register_path.read_bytes()
            source_sha = hashlib.sha256(source_bytes).hexdigest()
            constraint_bindings = opportunity_foundry_review.get('customer_constraint_source_bindings') or []
            exact_constraint_bindings = []
            for binding in constraint_bindings:
                start, end = binding.get('source_byte_start'), binding.get('source_byte_end_exclusive')
                span = source_bytes[start:end] if isinstance(start, int) and isinstance(end, int) and 0 <= start < end <= len(source_bytes) else b''
                statement = str(binding.get('statement') or '')
                exact_constraint_bindings.append(bool(span)
                    and binding.get('source_file_sha256') == source_sha
                    and hashlib.sha256(span).hexdigest() == binding.get('source_row_sha256')
                    and hashlib.sha256(statement.encode('utf-8')).hexdigest() == binding.get('source_statement_sha256')
                    and statement.encode('utf-8') in span)
            candidates = opportunity_foundry_review.get('ranked_opportunity_hypotheses') or []
            declared = {row.get('path'): row.get('sha256') for row in native_receipt.get('native_receipt', {}).get('artifacts') or []}
            html_text = review_path.read_text(encoding='utf-8')
            required_controls = ("id='filter'", "data-field='reviewer_decision'", "data-field='test_method'",
                                 "data-field='sample_scope'", "data-field='success_criteria'",
                                 "data-field='max_test_cost_zar'", "data-field='reviewer_role'",
                                 "data-field='reviewed_at_iso8601'", "source_record_bindings",
                                 "exceeds customer-stated cap", "OPPORTUNITY_FOUNDRY_REVIEW.csv")
            allocated = sum(float(row.get('max_test_cost_zar') or 0) for row in candidates)
            cap = opportunity_foundry_review.get('customer_budget_cap_zar')
            if (native_receipt.get('schema') != 'dio.native_customer_packet.execution.v1'
                    or native_receipt.get('product_name') != 'Opportunity Foundry'
                    or route_receipt.get('product_name') != 'Opportunity Foundry'
                    or route_receipt.get('terminal_artifact_kind') != 'ranked_opportunity_hypotheses'
                    or route_receipt.get('release_authorized') is not False
                    or route_receipt.get('external_effects') is not False
                    or route_receipt.get('commercial_validation') != 'UNPROVED'
                    or opportunity_foundry_review.get('schema') != 'dio.opportunity_foundry.professional_output.v1'
                    or opportunity_foundry_review.get('customer_source', {}).get('sha256') != source_sha
                    or len(constraint_bindings) != len(list(csv.DictReader(register_path.open(encoding='utf-8-sig', newline=''))))
                    or not exact_constraint_bindings or not all(exact_constraint_bindings)
                    or len(candidates) != 3 or [row.get('rank') for row in candidates] != [1, 2, 3]
                    or (cap is not None and allocated > float(cap))
                    or any(row.get('ranking_basis') != 'discovery title overlap; not market attractiveness' for row in candidates)
                    or opportunity_foundry_review.get('market_demand_claimed') is not False
                    or opportunity_foundry_review.get('willingness_to_pay_proved') is not False
                    or opportunity_foundry_review.get('authority_created') is not False
                    or output_receipt.get('executor_id') != 'opportunity_foundry_validation_sequence_v3'
                    or output_receipt.get('human_review_gate') != 'NEEDS_YOU'
                    or output_receipt.get('external_release_gate') != 'REFUSE'
                    or output_receipt.get('authority_created') is not False
                    or output_receipt.get('external_effects') is not False
                    or any(declared.get(path.name) != digest_file(path) for path in (result_path, brief_path, review_path))
                    or not all(token in html_text for token in required_controls)):
                raise ValueError('Opportunity Foundry review plan is stale, source-unbound, or crossed a customer-authority boundary')
            for required_artifact in required:
                product_specific_refs.append(register(required_artifact))
            product_specific_refs.append(register(ROOT / 'products/professional_evidence_native.py'))
            changes.append(f'Opportunity Foundry now byte-binds all {len(constraint_bindings)} customer constraints and provides an offline review surface for {len(candidates)} validation hypotheses, with editable methods, sample scope, success criteria, decisions, and allocation ceilings. Current sequence ranks complexity; it does not claim market attractiveness or demand.')
            limits.append('Proposed budget allocations are customer-owned planning inputs, not quotations or spend authorization. Market observations, buyer demand and willingness to pay are unproved; edits remain local until exported and do not schedule a pilot.')
            disposition = 'CURRENT_HELD_EXECUTION_VERIFIED'
        profile_review_surface = None
        if name in EVIDENCE_PROFILE_REVIEW_SURFACE_PRODUCTS and EVIDENCE_PROFILE_REVIEW_SURFACE_BATCH.is_dir():
            profile_slug = re.sub(r'[^a-z0-9]+', '-', name.lower()).strip('-')
            profile_case = EVIDENCE_PROFILE_REVIEW_SURFACE_BATCH / profile_slug / profile_slug
            profile_exec = profile_case / 'EXECUTION'
            route_receipt_path = profile_case / 'PROFESSIONAL_EVIDENCE_RECEIPT.json'
            pack_path = next(iter(profile_exec.glob('*_REVIEW_PACK.json')), None)
            html_path = next(iter(profile_exec.glob('*_REVIEW_PACK.html')), None)
            processing_path = next(iter(profile_exec.glob('*_PROCESSING_RECEIPT.json')), None)
            proof_path = profile_exec / 'PROOF_MANIFEST.json'
            register_path = profile_case / 'CUSTOMER_PACKET/SOURCES/02_evidence_register.csv'
            required = [route_receipt_path, pack_path, html_path, processing_path, proof_path, register_path]
            if any(path is None or not path.is_file() for path in required):
                raise ValueError(f'{name} interactive evidence-review route is missing a required artifact')
            route_receipt = read_json(route_receipt_path)
            review_pack = read_json(pack_path)
            processing_receipt = read_json(processing_path)
            proof = read_json(proof_path)
            register_bytes = register_path.read_bytes()
            register_sha = hashlib.sha256(register_bytes).hexdigest()
            with register_path.open(encoding='utf-8-sig', newline='') as handle:
                source_rows = {row.get('record_id', ''): row for row in csv.DictReader(handle)}
            packet_dir = profile_case / 'CUSTOMER_PACKET'
            provenance_checks = []
            for matrix_row in review_pack.get('requirement_evidence_matrix') or []:
                for binding in matrix_row.get('source_provenance') or []:
                    ref = str(binding.get('source_ref') or '')
                    file_ref = ref.removeprefix('customer-packet://').split('#', 1)[0]
                    record_id = ref.split('#', 1)[1] if '#' in ref else ''
                    source_row = source_rows.get(record_id, {})
                    start, end = binding.get('source_byte_start'), binding.get('source_byte_end_exclusive')
                    relative_source = Path(file_ref)
                    safe_source = not relative_source.is_absolute() and '..' not in relative_source.parts
                    source_path = packet_dir / relative_source if safe_source else packet_dir / '__invalid_source__'
                    source_bytes = source_path.read_bytes() if source_path.is_file() else b''
                    span = source_bytes[start:end] if isinstance(start, int) and isinstance(end, int) and 0 <= start < end <= len(source_bytes) else b''
                    statement = str(source_row.get('customer_supplied_record') or '').strip()
                    statement_hash_matches = (
                        hashlib.sha256(statement.encode('utf-8')).hexdigest() == binding.get('source_statement_sha256')
                        if file_ref == 'SOURCES/02_evidence_register.csv' and statement
                        else bool(re.fullmatch(r'[0-9a-f]{64}', str(binding.get('source_statement_sha256') or '')))
                    )
                    provenance_checks.append(bool(span) and safe_source
                        and hashlib.sha256(source_bytes).hexdigest() == binding.get('source_file_sha256')
                        and (file_ref != 'SOURCES/02_evidence_register.csv' or binding.get('source_file_sha256') == register_sha)
                        and hashlib.sha256(span).hexdigest() == binding.get('source_row_sha256')
                        and statement_hash_matches
                        and (not statement or statement.encode('utf-8') in span))
            html_text = html_path.read_text(encoding='utf-8')
            proof_html = next((row for row in proof.get('artifacts') or [] if row.get('filename') == html_path.name), {})
            declared = {row.get('path'): row.get('sha256') for row in route_receipt.get('artifacts') or []}
            matrix = review_pack.get('requirement_evidence_matrix') or []
            if (route_receipt.get('status') != 'PASS_FULL_PIPELINE'
                    or route_receipt.get('human_review_required') is not True
                    or route_receipt.get('external_publication') != 'REFUSE'
                    or route_receipt.get('authority_created') is not False
                    or route_receipt.get('external_effects') is not False
                    or processing_receipt.get('internal_processing') != 'COMPLETE'
                    or processing_receipt.get('human_review_gate') != 'NEEDS_YOU'
                    or processing_receipt.get('external_release_gate') != 'REFUSE'
                    or processing_receipt.get('domain_decision_created') is not False
                    or processing_receipt.get('authority_created') is not False
                    or processing_receipt.get('external_effects') is not False
                    or review_pack.get('human_review', {}).get('final_domain_decision') != 'NEEDS_YOU'
                    or review_pack.get('external_release') != 'REFUSE'
                    or not matrix or not provenance_checks or not all(provenance_checks)
                    or proof_html.get('sha256') != digest_file(html_path)
                    or declared.get(f'EXECUTION/{html_path.name}') != digest_file(html_path)
                    or len(re.findall(r"data-field='reviewer_disposition'", html_text)) != len(matrix)
                    or not all(token in html_text for token in ("id='filter'", 'EVIDENCE_REVIEW_WORKSHEET.csv', "role='status'"))):
                raise ValueError(f'{name} evidence-review surface is stale, source-unbound, or crossed its held boundary')
            profile_review_surface = review_pack
            for required_artifact in required:
                product_specific_refs.append(register(required_artifact))
            changes.append(f'{name} now has an interactive requirement review register with per-source hashes and byte spans, open challenge details, blank reviewer dispositions, rationale and follow-up fields, plus a downloadable CSV worksheet. No reviewer note changes evidence state or authorizes release.')
            limits.append('Source hashes establish which supplied record was referenced; they do not verify its truth, authority, completeness, applicability, or sufficiency. Final domain decisions and external release remain separate human decisions.')
            disposition = 'CURRENT_HELD_EXECUTION_VERIFIED'
        ai_trust_review = None
        ai_trust_slugs = {
            'Agent Authority': ('agent-authority', 'agent-authority/agent-authority', 'EXECUTION'),
            'ChangeProof': ('changeproof', 'changeproof/changeproof', 'EXECUTION'),
            'DIO AI Assurance': ('dio-ai-assurance', 'dio-ai-assurance', 'EXECUTION/component_aitrustproof'),
        }
        if name in ai_trust_slugs and AI_TRUST_REVIEW_SURFACE_BATCH.is_dir():
            folder, case_rel, execution_rel = ai_trust_slugs[name]
            case_root = AI_TRUST_REVIEW_SURFACE_BATCH / case_rel
            execution_root = case_root / execution_rel
            dossier_json = execution_root / 'AI_TRUST_DOSSIER.json'
            dossier_html = execution_root / 'AI_TRUST_DOSSIER.html'
            ai_receipt_path = execution_root / 'AI_TRUST_RECEIPT.json'
            seraph_path = execution_root / 'SERAPH_CHALLENGE_RECEIPT.json'
            proof_path = execution_root / 'PROOF_MANIFEST.json'
            route_path = case_root / ('NATIVE_CUSTOMER_PACKET_RECEIPT.json' if name == 'DIO AI Assurance' else 'PROFESSIONAL_EVIDENCE_RECEIPT.json')
            required = [dossier_json, dossier_html, ai_receipt_path, seraph_path, proof_path, route_path]
            if any(not path.is_file() for path in required):
                raise ValueError(f'{name} AI Trust customer review surface is missing a required artifact')
            dossier = read_json(dossier_json)
            ai_receipt = read_json(ai_receipt_path)
            seraph_receipt = read_json(seraph_path)
            proof = read_json(proof_path)
            route_receipt = read_json(route_path)
            html_text = dossier_html.read_text(encoding='utf-8')
            proof_artifacts = {row.get('filename'): row.get('sha256') for row in proof.get('artifacts') or []}
            route_artifacts = {row.get('path'): row.get('sha256') for row in route_receipt.get('artifacts') or []}
            relative_html = str(dossier_html.relative_to(case_root)).replace('\\', '/')
            challenge_digest = digest_file(seraph_path)
            # Declarations from the evidence register must resolve to the exact supplied CSV bytes.
            declarations = (dossier.get('provenance_manifest') or {}).get('customer_declarations') or []
            source_checks = []
            if name in {'Agent Authority', 'ChangeProof'}:
                register_path = case_root / 'CUSTOMER_PACKET/SOURCES/02_evidence_register.csv'
                source_bytes = register_path.read_bytes() if register_path.is_file() else b''
                lines = source_bytes.splitlines(keepends=True)
                offsets, cursor = {}, len(lines[0]) if lines else 0
                for raw_line in lines[1:]:
                    line = raw_line.rstrip(b'\\r\\n')
                    if line:
                        try:
                            record_id = next(csv.reader([line.decode('utf-8')]))[0]
                            offsets[record_id] = (cursor, cursor + len(line))
                        except (UnicodeDecodeError, IndexError):
                            pass
                    cursor += len(raw_line)
                with register_path.open(encoding='utf-8-sig', newline='') as handle:
                    source_rows = {row.get('record_id', ''): row for row in csv.DictReader(handle)}
                for declaration in declarations:
                    record_id = str(declaration.get('source_locator') or '')
                    start, end = declaration.get('source_byte_start'), declaration.get('source_byte_end_exclusive')
                    expected_offsets = offsets.get(record_id)
                    statement = str(source_rows.get(record_id, {}).get('customer_supplied_record') or '').strip()
                    span = source_bytes[start:end] if isinstance(start, int) and isinstance(end, int) and 0 <= start < end <= len(source_bytes) else b''
                    source_checks.append(bool(expected_offsets and expected_offsets == (start, end) and span)
                        and hashlib.sha256(source_bytes).hexdigest() == declaration.get('source_file_sha256')
                        and hashlib.sha256(span).hexdigest() == declaration.get('source_row_sha256')
                        and hashlib.sha256(statement.encode('utf-8')).hexdigest() == declaration.get('source_statement_sha256')
                        and statement.encode('utf-8') in span)
            route_ok = (
                (route_receipt.get('status') == 'PASS_FULL_PIPELINE' if name != 'DIO AI Assurance' else route_receipt.get('release_authorized') is False)
                and route_receipt.get('human_review_required') is True
                and route_receipt.get('external_effects') is False
                and route_receipt.get('authority_created') is False
                if name != 'DIO AI Assurance' else
                route_receipt.get('release_authorized') is False and route_receipt.get('external_effects') is False
            )
            if (not route_ok
                    or ai_receipt.get('human_gate') != 'NEEDS_YOU'
                    or ai_receipt.get('external_release_gate') != 'REFUSE'
                    or ai_receipt.get('authority_created') is not False
                    or ai_receipt.get('external_effects') is not False
                    or ai_receipt.get('seraph_verdict') != (seraph_receipt.get('verdict') or seraph_receipt.get('challenge_verdict'))
                    or not ai_receipt.get('seraph_coverage_state')
                    or proof_artifacts.get(dossier_html.name) != digest_file(dossier_html)
                    or proof_artifacts.get(seraph_path.name) != challenge_digest
                    or route_artifacts.get(relative_html) != digest_file(dossier_html)
                    or (name in {'Agent Authority', 'ChangeProof'} and (not declarations or not source_checks or not all(source_checks)))
                    or not all(token in html_text for token in ("data-field='reviewer_disposition'", "data-field='reviewer_name'", 'AI_TRUST_REVIEW_WORKSHEET.csv', 'Seraph challenge findings'))):
                raise ValueError(f'{name} AI Trust review surface is stale, source-unbound, or crossed its held authority boundary')
            ai_trust_review = dossier
            for required_artifact in required:
                product_specific_refs.append(register(required_artifact))
            if name in {'Agent Authority', 'ChangeProof'}:
                product_specific_refs.append(register(case_root / 'CUSTOMER_PACKET/SOURCES/02_evidence_register.csv'))
            changes.append(f'{name} now exposes its AI Trust evidence as an offline review surface with editable reviewer disposition and rationale, customer declaration bindings where present, Seraph challenge findings, and a downloadable worksheet. Current route evidence remains held for human review.')
            limits.append('Seraph findings and telemetry coverage describe this supplied case only; embedded signer identity, telemetry completeness, live behavior, source truth, domain conclusions, and release authority remain unverified.')
            disposition = 'CURRENT_HELD_EXECUTION_VERIFIED'
        if name in EIGHT_SPECIALIST_QUALIFICATION_PRODUCTS and EIGHT_SPECIALIST_QUALIFICATION_RUN.is_dir():
            specialist_qualification_root = EIGHT_SPECIALIST_QUALIFICATION_RUN / name.lower()
            batch_receipt_path = EIGHT_SPECIALIST_QUALIFICATION_RUN / 'EIGHT_SPECIALIST_QUALIFICATION_RECEIPT.json'
            if not batch_receipt_path.is_file():
                raise ValueError('eight-specialist qualification receipt is missing')
            batch_receipt = read_json(batch_receipt_path)
            journeys = [row for row in batch_receipt.get('journeys') or [] if row.get('product_name') == name]
            tamper = [row for row in batch_receipt.get('tamper_refusals') or [] if row.get('product_name') == name]
            if (batch_receipt.get('schema') != 'dio.eight_specialist_qualification.v1'
                    or len(journeys) != 3 or {row.get('scenario') for row in journeys} != {'normal', 'messy', 'adversarial'}
                    or any(row.get('status') != 'PASS' or row.get('release_authorized') is not False
                           or row.get('professional_approval') != 'NOT_GRANTED' for row in journeys)
                    or len(tamper) != 1 or tamper[0].get('status') != 'REFUSAL_VERIFIED'
                    or batch_receipt.get('commercial_validation') != 'UNPROVED'
                    or batch_receipt.get('external_effects') is not False):
                raise ValueError(f'{name} eight-specialist scenario evidence is incomplete or crosses its held boundary')
            product_specific_refs.append(register(batch_receipt_path))
            grade7_correction = ROOT / 'deliverables/homs_random_grade_exam_set_20261101/GRADE07_CONTENT_CORRECTION_20261102.json'
            if grade7_correction.is_file():
                product_specific_refs.append(register(grade7_correction))
                changes.append('Grade 7 Question 1.1 now names all four items and explicitly includes production input, business expense, and sales revenue categories. Its six one-mark memo points align to the four classifications and two requested explanations; the corrected V45 exam and memo remain educator-held drafts.')
            for scenario in ('normal', 'messy', 'adversarial'):
                package_root = specialist_qualification_root / scenario
                package_path = package_root / 'CUSTOMER_PACKAGE_RECEIPT.json'
                if not package_path.is_file():
                    raise ValueError(f'{name} {scenario} customer package receipt is missing')
                package = read_json(package_path)
                if package.get('professional_approval') != 'NOT_GRANTED' or package.get('authority_created') is not False:
                    raise ValueError(f'{name} {scenario} customer package crosses its human-review boundary')
                for output_artifact in package.get('outputs') or []:
                    artifact_path = package_root / str(output_artifact.get('path') or '')
                    if not artifact_path.is_file() or digest_file(artifact_path) != output_artifact.get('sha256'):
                        raise ValueError(f'{name} {scenario} output failed receipt hash verification')
                    product_specific_refs.append(register(artifact_path, output_artifact.get('sha256')))
                product_specific_refs.append(register(package_path))
            changes.append(f'{name} now passes source-bound normal, missing-record and challenged-source customer scenarios, with tampered source hashes refused. Output documents and specialist work queues are hash-verified; professional approval and release remain disabled.')
            limits.append('These are controlled synthetic cases. They establish product behavior and source custody only; they do not establish domain findings, customer acceptance or professional sign-off.')
            disposition = 'CURRENT_HELD_EXECUTION_VERIFIED'
        if name == 'FundingFinder' and 'fundingfinder_live_services_seta_refresh' in run_groups:
            group = run_groups['fundingfinder_live_services_seta_refresh']
            product_specific_refs.extend([group['source'], group['route_receipt']])
            product_specific_refs.append(register(FUNDING_FINDER_SERVICESETA_PACKET))
            changes.append('FundingFinder’s refreshed Services SETA route binds the revised 15 November 2026 deadline and current application-system unavailability to captured official sources; the three-window review applies the same update to DG-03, SP-04 and SP-01.')
            limits = ['Applicant category, selected programme/project, Annexure A or focus-area fit, learner-age composition and submission readiness lack applicant evidence. The application system is currently unavailable; monitor Services SETA for application arrangements. No eligibility certification, award likelihood or application submission is produced.']
        if name == 'Corporate Readiness' and CORPORATE_READINESS_ACTION_RUN.is_dir():
            run_dir = CORPORATE_READINESS_ACTION_RUN
            package_path = run_dir / 'CUSTOMER_PACKAGE_RECEIPT.json'
            register_path = run_dir / 'CORPORATE_CUSTOMER_ACTION_REGISTER.json'
            csv_path = run_dir / 'CORPORATE_CUSTOMER_ACTION_REGISTER.csv'
            bindings_path = run_dir / 'SOURCE_BINDINGS.json'
            if not all(path.is_file() for path in (package_path, register_path, csv_path, bindings_path)):
                raise ValueError('Corporate Readiness action register package is incomplete')
            package = read_json(package_path)
            action_register = read_json(register_path)
            source_bindings = read_json(bindings_path)
            declared = {row['path']: row.get('sha256') for row in package.get('outputs') or []}
            with csv_path.open('r', encoding='utf-8-sig', newline='') as handle:
                action_csv_rows = list(csv.DictReader(handle))
            if (action_register.get('schema') != 'dio.corporate_readiness.customer_action_register.v1'
                    or len(action_register.get('actions') or []) != 5
                    or len(action_csv_rows) != 5
                    or action_register.get('owner_unassigned_count') != 5
                    or action_register.get('target_date_unsupplied_count') != 5
                    or action_register.get('legal_deadline_calculated') is not False
                    or action_register.get('filing_authorized') is not False
                    or package.get('professional_approval') != 'NOT_GRANTED'
                    or package.get('authority_created') is not False
                    or declared.get(register_path.name) != digest_file(register_path)
                    or declared.get(csv_path.name) != digest_file(csv_path)):
                raise ValueError('Corporate Readiness sample action register is stale or crossed a legal/filing boundary')
            for relative, sha256 in declared.items():
                artifact_path = run_dir / relative
                if artifact_path.is_file():
                    product_specific_refs.append(register(artifact_path, sha256))
            product_specific_refs.append(register(package_path))
            assigned_demo = CORPORATE_READINESS_ACTION_ASSIGNMENT_DEMO / 'EXECUTION'
            assigned_packet_path = CORPORATE_READINESS_ACTION_ASSIGNMENT_DEMO / 'CUSTOMER_PACKET.json'
            assigned_register_path = assigned_demo / 'CORPORATE_CUSTOMER_ACTION_REGISTER.json'
            assigned_package_path = assigned_demo / 'CUSTOMER_PACKAGE_RECEIPT.json'
            assigned_bindings_path = assigned_demo / 'SOURCE_BINDINGS.json'
            if not all(path.is_file() for path in (assigned_packet_path, assigned_register_path, assigned_package_path, assigned_bindings_path)):
                raise ValueError('Corporate Readiness source-bound owner/date assignment demo is incomplete')
            assigned_packet = read_json(assigned_packet_path)
            assigned_register = read_json(assigned_register_path)
            assigned_package = read_json(assigned_package_path)
            assigned_bindings = read_json(assigned_bindings_path)
            assigned_action = next((row for row in assigned_register.get('actions') or [] if row.get('requirement_id') == 'R2'), {})
            owner_anchor = assigned_action.get('owner_source_anchor') or {}
            date_anchor = assigned_action.get('target_date_source_anchor') or {}
            assigned_declared = {row['path']: row.get('sha256') for row in assigned_package.get('outputs') or []}
            if (assigned_action.get('owner') != 'Finance Lead'
                    or assigned_action.get('customer_target_date') != '2026-11-15'
                    or owner_anchor.get('source_id') != 'ACTION_PLAN'
                    or 'Finance Lead' not in owner_anchor.get('quote', '')
                    or date_anchor.get('source_id') != 'ACTION_PLAN'
                    or '2026-11-15' not in date_anchor.get('quote', '')
                    or not any(row.get('binding_kind') == 'corporate_action_owner'
                               and row.get('binding_id') == 'R2:owner'
                               and row.get('source_anchor', {}).get('source_quote_sha256') == owner_anchor.get('source_quote_sha256')
                               for row in assigned_bindings.get('bindings') or [])
                    or not any(row.get('binding_kind') == 'corporate_action_target_date'
                               and row.get('binding_id') == 'R2:target_date'
                               and row.get('source_anchor', {}).get('source_quote_sha256') == date_anchor.get('source_quote_sha256')
                               for row in assigned_bindings.get('bindings') or [])
                    or assigned_action.get('date_basis') != 'CUSTOMER_STATED_TARGET_ONLY'
                    or assigned_register.get('legal_deadline_calculated') is not False
                    or assigned_register.get('filing_authorized') is not False
                    or assigned_package.get('professional_approval') != 'NOT_GRANTED'
                    or assigned_declared.get('CORPORATE_CUSTOMER_ACTION_REGISTER.json') != digest_file(assigned_register_path)):
                raise ValueError('Corporate Readiness owner/date mapping failed its source and authority boundaries')
            product_specific_refs.append(register(assigned_packet_path))
            for relative, sha256 in assigned_declared.items():
                artifact_path = assigned_demo / relative
                if artifact_path.is_file():
                    product_specific_refs.append(register(artifact_path, sha256))
            product_specific_refs.append(register(assigned_package_path))
            changes.append('Corporate Readiness now includes a five-row editable action register with source-backed requirement states, document requests, blank owner/date fields, and customer-stated dates only. The baseline packet leaves all owners and dates unassigned; a second synthetic route source-binds a named owner and target date to exact source quotations. No statutory deadline, filing authorization or corporate-record truth is inferred.')
            limits.append('The action register organizes customer requirements and customer-planned follow-up only. Company records, requirement applicability, legal deadlines, filing sufficiency and company compliance remain unverified; an authorized reviewer must confirm them.')
            disposition = 'CURRENT_HELD_EXECUTION_VERIFIED'
        if name == 'EntrepreneurProof' and ENTREPRENEURPROOF_SOURCE_ISSUE_RUN.is_dir():
            issue_run = ENTREPRENEURPROOF_SOURCE_ISSUE_RUN
            issue_package_path = issue_run / 'CUSTOMER_PACKAGE_RECEIPT.json'
            issue_artifact_path = issue_run / 'READINESS_SOURCE_REPORTED_ISSUES.json'
            issue_bindings_path = issue_run / 'SOURCE_BINDINGS.json'
            issue_matrix_path = issue_run / 'READINESS_EVIDENCE_MATRIX.json'
            issue_packet_path = issue_run / 'SOURCE_PACKET.json'
            if not all(path.is_file() for path in (issue_package_path, issue_artifact_path, issue_bindings_path, issue_matrix_path, issue_packet_path)):
                raise ValueError('EntrepreneurProof source-reported issue handoff is incomplete')
            issue_package = read_json(issue_package_path)
            issue_artifact = read_json(issue_artifact_path)
            issue_bindings = read_json(issue_bindings_path)
            issue_matrix = read_json(issue_matrix_path)
            issue_packet = read_json(issue_packet_path)
            declared = {row['path']: row.get('sha256') for row in issue_package.get('outputs') or []}
            sources = {row['source_id']: row for row in issue_packet.get('sources') or []}
            issue_rows = issue_artifact.get('issues') or []
            binding_rows = [row for row in issue_bindings.get('bindings') or [] if row.get('binding_kind') == 'source_reported_issue']
            if (issue_artifact.get('schema') != 'dio.readiness.source_reported_issues.v1'
                    or len(issue_rows) != 4 or len(binding_rows) != 4
                    or issue_artifact.get('human_review_required') is not True
                    or 'not independently verified' not in issue_artifact.get('interpretation', '')
                    or issue_package.get('professional_approval') != 'NOT_GRANTED'
                    or issue_package.get('authority_created') is not False
                    or declared.get(issue_artifact_path.name) != digest_file(issue_artifact_path)
                    or declared.get(issue_bindings_path.name) != digest_file(issue_bindings_path)):
                raise ValueError('EntrepreneurProof source-reported issue artifact is stale or crosses its claim boundary')
            for row in issue_rows:
                anchor = row.get('source_anchor') or {}
                source = sources.get(anchor.get('source_id'))
                raw = (source or {}).get('text', '').encode('utf-8')
                start, end = anchor.get('source_byte_start'), anchor.get('source_byte_end_exclusive')
                quote = anchor.get('quote', '').encode('utf-8')
                if (row.get('state') != 'SOURCE_REPORTED_UNVERIFIED' or not source
                        or hashlib.sha256(raw).hexdigest() != anchor.get('source_sha256')
                        or not isinstance(start, int) or not isinstance(end, int) or raw[start:end] != quote
                        or hashlib.sha256(quote).hexdigest() != anchor.get('source_quote_sha256')
                        or not any(binding.get('binding_id') == row.get('issue_id')
                                   and (binding.get('source_anchor') or {}).get('source_quote_sha256') == anchor.get('source_quote_sha256')
                                   for binding in binding_rows)):
                    raise ValueError('EntrepreneurProof issue quote failed exact source-byte lineage')
            if [(row['requirement_id'], row['state'], row['supporting_evidence_ids']) for row in issue_matrix] != [
                    ('R1', 'RECEIVED_FOR_REVIEW', ['E1']), ('R2', 'PARTIAL_FOR_REVIEW', ['E2']),
                    ('R3', 'RECEIVED_FOR_REVIEW', ['E3']), ('R4', 'PARTIAL_FOR_REVIEW', ['E4']), ('R5', 'MISSING', [])]:
                raise ValueError('EntrepreneurProof discovery and operating-capacity coverage states are stale or inaccurate')
            for relative, sha256 in declared.items():
                artifact_path = issue_run / relative
                if artifact_path.is_file():
                    product_specific_refs.append(register(artifact_path, sha256))
            product_specific_refs.append(register(issue_package_path))
            changes.append('EntrepreneurProof now retains four source-reported concerns with exact source-byte anchors. Customer-discovery evidence and weekend capacity are marked partial because source notes say supporting records and permissions are absent; reported pricing/cost assumptions remain available for review but unverified.')
            limits.append('Source-reported concerns are customer-provided statements, not independently verified findings. The synthetic route does not establish customer acceptance, business viability, compliance or professional approval.')
            disposition = 'CURRENT_HELD_EXECUTION_VERIFIED'
        readiness_issue_run = READINESS_SOURCE_ISSUE_RUNS.get(name)
        if readiness_issue_run and readiness_issue_run.is_dir():
            package_path = readiness_issue_run / 'CUSTOMER_PACKAGE_RECEIPT.json'
            issue_path = readiness_issue_run / 'READINESS_SOURCE_REPORTED_ISSUES.json'
            bindings_path = readiness_issue_run / 'SOURCE_BINDINGS.json'
            matrix_path = readiness_issue_run / 'READINESS_EVIDENCE_MATRIX.json'
            packet_path = readiness_issue_run / 'SOURCE_PACKET.json'
            if not all(path.is_file() for path in (package_path, issue_path, bindings_path, matrix_path, packet_path)):
                raise ValueError(f'{name} source-reported issue handoff is incomplete')
            package = read_json(package_path)
            issue_artifact = read_json(issue_path)
            bindings = read_json(bindings_path)
            matrix = read_json(matrix_path)
            packet = read_json(packet_path)
            declared = {row['path']: row.get('sha256') for row in package.get('outputs') or []}
            source_rows = {row['source_id']: row for row in packet.get('sources') or []}
            issues = issue_artifact.get('issues') or []
            issue_bindings = [row for row in bindings.get('bindings') or [] if row.get('binding_kind') == 'source_reported_issue']
            if (issue_artifact.get('schema') != 'dio.readiness.source_reported_issues.v1'
                    or not issues or len(issues) != len(issue_bindings)
                    or issue_artifact.get('human_review_required') is not True
                    or 'not independently verified' not in issue_artifact.get('interpretation', '')
                    or package.get('professional_approval') != 'NOT_GRANTED'
                    or package.get('authority_created') is not False
                    or declared.get(issue_path.name) != digest_file(issue_path)
                    or declared.get(bindings_path.name) != digest_file(bindings_path)):
                raise ValueError(f'{name} issue handoff is stale, unbound, or crosses its claim boundary')
            for issue in issues:
                anchor = issue.get('source_anchor') or {}
                source = source_rows.get(anchor.get('source_id'))
                raw = (source or {}).get('text', '').encode('utf-8')
                quote = anchor.get('quote', '').encode('utf-8')
                start, end = anchor.get('source_byte_start'), anchor.get('source_byte_end_exclusive')
                if (issue.get('state') != 'SOURCE_REPORTED_UNVERIFIED' or not source
                        or hashlib.sha256(raw).hexdigest() != anchor.get('source_sha256')
                        or not isinstance(start, int) or not isinstance(end, int) or raw[start:end] != quote
                        or hashlib.sha256(quote).hexdigest() != anchor.get('source_quote_sha256')
                        or not any(row.get('binding_id') == issue.get('issue_id')
                                   and (row.get('source_anchor') or {}).get('source_quote_sha256') == anchor.get('source_quote_sha256')
                                   for row in issue_bindings)):
                    raise ValueError(f'{name} issue quote failed exact source-byte lineage')
            if any(row.get('state') not in {'RECEIVED_FOR_REVIEW', 'PARTIAL_FOR_REVIEW', 'MISSING'} for row in matrix):
                raise ValueError(f'{name} source issues changed or corrupted documentary evidence states')
            if name in {'Finance Readiness', 'Finance Readiness Studio'}:
                r2 = next((row for row in matrix if row.get('requirement_id') == 'R2'), {})
                native = read_json(readiness_issue_run / 'EVIDEX_READINESS_RECEIPT.json')
                actions = read_json(readiness_issue_run / 'DOCUMENT_REQUESTS.json')
                r2_action = next((row for row in actions if row.get('requirement_id') == 'R2'), {})
                if (package.get('product_name') != name
                        or r2.get('state') != 'PARTIAL_FOR_REVIEW'
                        or r2.get('supporting_evidence_ids') != ['E2']
                        or r2.get('coverage_basis_ids') != ['ISSUE-001', 'R2']
                        or not any('twelve-month' in note.casefold() and 'july through september 2026' in note.casefold()
                                   for note in r2.get('coverage_notes', []))
                        or native.get('mandatory_gap_count') != 2
                        or native.get('mandatory_incomplete_count') != 3
                        or native.get('readiness_state') != 'EVIDENCE_GAPS_PRESENT'
                        or package.get('partial_coverage_count') != 1
                        or package.get('mandatory_incomplete_count') != 3
                        or r2_action.get('requirement_id') != 'R2'):
                    raise ValueError(f'{name} failed the partial twelve-month bank-statement coverage handoff')
            elif name == 'Corporate Readiness':
                by_requirement = {row.get('requirement_id'): row for row in matrix}
                native = read_json(readiness_issue_run / 'EVIDEX_READINESS_RECEIPT.json')
                actions = read_json(readiness_issue_run / 'DOCUMENT_REQUESTS.json')
                if (package.get('product_name') != name
                        or len(issues) != 4
                        or by_requirement.get('R1', {}).get('state') != 'RECEIVED_FOR_REVIEW'
                        or by_requirement.get('R1', {}).get('supporting_evidence_ids') != ['E1']
                        or 'two directors listed' not in next((row.get('source_anchor', {}).get('quote', '') for row in bindings.get('bindings', []) if row.get('binding_id') == 'E1'), '')
                        or by_requirement.get('R2', {}).get('state') != 'MISSING'
                        or by_requirement.get('R3', {}).get('state') != 'MISSING'
                        or by_requirement.get('R4', {}).get('state') != 'PARTIAL_FOR_REVIEW'
                        or by_requirement.get('R4', {}).get('coverage_basis_ids') != ['ISSUE-003', 'R4']
                        or by_requirement.get('R5', {}).get('state') != 'PARTIAL_FOR_REVIEW'
                        or by_requirement.get('R5', {}).get('coverage_basis_ids') != ['ISSUE-004', 'R5']
                        or native.get('mandatory_gap_count') != 2
                        or native.get('mandatory_incomplete_count') != 4
                        or package.get('fully_received_count') != 1
                        or package.get('partial_coverage_count') != 2
                        or package.get('mandatory_incomplete_count') != 4
                        or {row.get('requirement_id') for row in actions} != {'R2', 'R3', 'R4', 'R5'}):
                    raise ValueError('Corporate Readiness failed director, account-ownership, or current-year statement completeness checks')
            elif name == 'InvestorProof':
                by_requirement = {row.get('requirement_id'): row for row in matrix}
                native = read_json(readiness_issue_run / 'EVIDEX_READINESS_RECEIPT.json')
                actions = read_json(readiness_issue_run / 'DOCUMENT_REQUESTS.json')
                if (package.get('product_name') != name or len(issues) != 2
                        or by_requirement.get('R2', {}).get('state') != 'PARTIAL_FOR_REVIEW'
                        or by_requirement.get('R2', {}).get('supporting_evidence_ids') != ['E2']
                        or by_requirement.get('R2', {}).get('coverage_basis_ids') != ['ISSUE-001', 'R2']
                        or by_requirement.get('R4', {}).get('state') != 'MISSING'
                        or by_requirement.get('R5', {}).get('state') != 'MISSING'
                        or native.get('mandatory_gap_count') != 2 or native.get('mandatory_incomplete_count') != 3
                        or package.get('fully_received_count') != 2 or package.get('partial_coverage_count') != 1
                        or package.get('mandatory_incomplete_count') != 3
                        or {row.get('requirement_id') for row in actions} != {'R2', 'R4', 'R5'}):
                    raise ValueError('InvestorProof failed current-cap-table coverage checks')
            elif name == 'POPIA Readiness':
                by_requirement = {row.get('requirement_id'): row for row in matrix}
                native = read_json(readiness_issue_run / 'EVIDEX_READINESS_RECEIPT.json')
                actions = read_json(readiness_issue_run / 'DOCUMENT_REQUESTS.json')
                e1_quote = next((row.get('source_anchor', {}).get('quote', '') for row in bindings.get('bindings', []) if row.get('binding_id') == 'E1'), '')
                if (package.get('product_name') != name or len(issues) != 3
                        or 'system owner is Customer Operations' not in e1_quote
                        or by_requirement.get('R1', {}).get('state') != 'RECEIVED_FOR_REVIEW'
                        or by_requirement.get('R2', {}).get('state') != 'RECEIVED_FOR_REVIEW'
                        or by_requirement.get('R3', {}).get('state') != 'PARTIAL_FOR_REVIEW'
                        or by_requirement.get('R3', {}).get('supporting_evidence_ids') != ['E3']
                        or by_requirement.get('R3', {}).get('coverage_basis_ids') != ['ISSUE-001', 'R3']
                        or by_requirement.get('R4', {}).get('state') != 'MISSING'
                        or by_requirement.get('R5', {}).get('state') != 'MISSING'
                        or native.get('mandatory_gap_count') != 2 or native.get('mandatory_incomplete_count') != 3
                        or package.get('fully_received_count') != 2 or package.get('partial_coverage_count') != 1
                        or package.get('mandatory_incomplete_count') != 3
                        or {row.get('requirement_id') for row in actions} != {'R3', 'R4', 'R5'}):
                    raise ValueError('POPIA Readiness failed owner-field or operator-agreement scope checks')
            elif name == 'EntrepreneurProof':
                by_requirement = {row.get('requirement_id'): row for row in matrix}
                native = read_json(readiness_issue_run / 'EVIDEX_READINESS_RECEIPT.json')
                actions = read_json(readiness_issue_run / 'DOCUMENT_REQUESTS.json')
                if (package.get('product_name') != name or len(issues) != 4
                        or by_requirement.get('R2', {}).get('state') != 'PARTIAL_FOR_REVIEW'
                        or by_requirement.get('R2', {}).get('coverage_basis_ids') != ['ISSUE-001', 'R2']
                        or by_requirement.get('R4', {}).get('state') != 'PARTIAL_FOR_REVIEW'
                        or by_requirement.get('R4', {}).get('supporting_evidence_ids') != ['E4']
                        or by_requirement.get('R4', {}).get('coverage_basis_ids') != ['ISSUE-003', 'R4']
                        or by_requirement.get('R5', {}).get('state') != 'MISSING'
                        or native.get('mandatory_gap_count') != 1 or native.get('mandatory_incomplete_count') != 3
                        or package.get('fully_received_count') != 2 or package.get('partial_coverage_count') != 2
                        or package.get('mandatory_incomplete_count') != 3
                        or {row.get('requirement_id') for row in actions} != {'R2', 'R4', 'R5'}):
                    raise ValueError('EntrepreneurProof failed discovery and operating-permission coverage checks')
            for relative, sha256 in declared.items():
                artifact_path = readiness_issue_run / relative
                if artifact_path.is_file():
                    product_specific_refs.append(register(artifact_path, sha256))
            product_specific_refs.append(register(package_path))
            if name == 'Corporate Readiness':
                changes.append('Corporate Readiness now matches the supplied profile quote to both company registration and the two listed directors. It marks the bank-account and current-year financial requirements partial where the source packet reports missing ownership verification and current-year statements; the source concerns remain unverified.')
            elif name in {'Finance Readiness', 'Finance Readiness Studio'}:
                changes.append(f'{name} retains {len(issues)} source-reported concern(s) in the reviewer handoff with exact source-byte anchors. The twelve-month bank-statement requirement is now partial because the supplied period covers July–September only and October is reported pending; the unverified concern is not treated as a verified finding.')
            elif name == 'InvestorProof':
                changes.append('InvestorProof now marks the founder spreadsheet as partial current-cap-table evidence because the source packet says a signed shareholder register and conversion schedule were not supplied. The percentages remain unverified customer assertions.')
            elif name == 'POPIA Readiness':
                changes.append('POPIA Readiness now marks the supplier-hosting statement as partial operator evidence because the source packet says the operator agreement and subprocessor schedule were not attached. The named vendor is not treated as proof of those records or of compliance.')
            else:
                changes.append(f'{name} now retains {len(issues)} source-reported concern(s) in the reviewer handoff with exact source-byte anchors. They remain unverified and are not treated as verified findings.')
            limits.append('Concerns are customer-provided statements, not independently verified findings. The synthetic route proves bounded artifact behavior only; customer acceptance, source truth and professional approval remain unestablished.')
            superseded_run = READINESS_SOURCE_ISSUE_SUPERSEDED_RUNS.get(name)
            if superseded_run and superseded_run.is_dir():
                old_package = read_json(superseded_run / 'CUSTOMER_PACKAGE_RECEIPT.json')
                old_declared = {row['path']: row.get('sha256') for row in old_package.get('outputs') or []}
                for relative, sha256 in old_declared.items():
                    historical_path = superseded_run / relative
                    if historical_path.is_file():
                        product_specific_refs.append(register(historical_path, sha256))
                product_specific_refs.append(register(superseded_run / 'CUSTOMER_PACKAGE_RECEIPT.json'))
                changes.append('The earlier V1 package is retained as superseded history; it classified any supplied R2 statement as received without representing the period shortfall.')
            disposition = 'CURRENT_HELD_EXECUTION_VERIFIED'
        issue_review_run = READINESS_ISSUE_REVIEW_SURFACES.get(name)
        if issue_review_run and issue_review_run.is_dir():
            receipt_path = issue_review_run / 'CUSTOMER_PACKAGE_RECEIPT.json'
            if not receipt_path.is_file():
                raise ValueError(f'{name} offline issue-review surface has no customer package receipt')
            package = read_json(receipt_path)
            declared = {row['path']: row.get('sha256') for row in package.get('outputs') or []}
            for filename in ('READINESS_SOURCE_REPORTED_ISSUES.json', 'READINESS_ISSUE_REVIEW.csv', 'READINESS_ISSUE_REVIEW.html'):
                path = issue_review_run / filename
                if not path.is_file() or declared.get(filename) != digest_file(path):
                    raise ValueError(f'{name} issue-review surface artifact is missing or not receipt-bound: {filename}')
                product_specific_refs.append(register(path, declared[filename]))
            if package.get('professional_approval') != 'NOT_GRANTED' or package.get('authority_created') is not False:
                raise ValueError(f'{name} issue-review surface crosses the human approval boundary')
            product_specific_refs.append(register(receipt_path))
            changes.append(f'{name} now includes an offline relevance and follow-up review page for source-reported concerns, with fixed source hashes and byte positions and blank reviewer decisions.')
            limits.append('The review page captures reviewer input only; the source statements remain unverified and the package grants no professional approval or release authority.')
        evidence_issue_run = EVIDENCE_SOURCE_ISSUE_RUNS.get(name)
        if evidence_issue_run and evidence_issue_run.is_dir():
            package_path = evidence_issue_run / 'CUSTOMER_PACKAGE_RECEIPT.json'
            issue_path = evidence_issue_run / 'SOURCE_REPORTED_ISSUES.json'
            packet_path = evidence_issue_run / 'SOURCE_PACKET.json'
            if not all(path.is_file() for path in (package_path, issue_path, packet_path)):
                raise ValueError(f'{name} source-reported issue review is incomplete')
            package = read_json(package_path)
            issue_artifact = read_json(issue_path)
            packet = read_json(packet_path)
            declared = {row['path']: row.get('sha256') for row in package.get('outputs') or []}
            sources = {row['source_id']: row for row in packet.get('sources') or []}
            issues = issue_artifact.get('issues') or []
            if (issue_artifact.get('schema') != 'dio.evidence_review.source_reported_issues.v1'
                    or not issues
                    or issue_artifact.get('human_review_required') is not True
                    or 'not been independently verified' not in issue_artifact.get('interpretation', '')
                    or package.get('professional_approval') != 'NOT_GRANTED'
                    or package.get('authority_created') is not False
                    or declared.get(issue_path.name) != digest_file(issue_path)):
                raise ValueError(f'{name} source-reported issue artifact is stale or crosses its review boundary')
            for issue in issues:
                anchor = issue.get('source_anchor') or {}
                source = sources.get(anchor.get('source_id'))
                raw = (source or {}).get('text', '').encode('utf-8')
                quote = anchor.get('quote', '').encode('utf-8')
                start, end = anchor.get('source_byte_start'), anchor.get('source_byte_end_exclusive')
                if (issue.get('state') != 'SOURCE_REPORTED_UNVERIFIED' or not source
                        or hashlib.sha256(raw).hexdigest() != anchor.get('source_sha256')
                        or not isinstance(start, int) or not isinstance(end, int) or raw[start:end] != quote
                        or hashlib.sha256(quote).hexdigest() != anchor.get('source_quote_sha256')):
                    raise ValueError(f'{name} source-reported concern failed exact source-byte lineage')
            for relative, sha256 in declared.items():
                artifact_path = evidence_issue_run / relative
                if artifact_path.is_file():
                    product_specific_refs.append(register(artifact_path, sha256))
            product_specific_refs.append(register(package_path))
            changes.append(f'{name} now carries {len(issues)} source-reported concern(s) with exact source-byte anchors and an explicit unverified review state; truth and domain conclusions remain open.')
            limits.append('Source-reported concerns remain unverified customer statements. The synthetic route and byte lineage do not establish source truth, domain conclusions, customer acceptance or professional approval.')
            disposition = 'CURRENT_HELD_EXECUTION_VERIFIED'
        if name == 'AI IncidentRoom' and AI_INCIDENTROOM_TIMELINE_RUN.is_dir():
            timeline_path = AI_INCIDENTROOM_TIMELINE_RUN / 'INCIDENT_LITERAL_TIME_MARKERS.json'
            timeline_evidence_path = AI_INCIDENTROOM_TIMELINE_RUN / 'INCIDENT_LITERAL_TIMELINE_EXECUTION_EVIDENCE.json'
            timeline_receipt_path = AI_INCIDENTROOM_TIMELINE_RUN / 'CUSTOMER_PACKAGE_RECEIPT.json'
            timeline_execution_path = AI_INCIDENTROOM_TIMELINE_RUN / 'CUSTOMER_EXECUTION_RECEIPT.json'
            timeline_packet_path = AI_INCIDENTROOM_TIMELINE_RUN / 'SOURCE_PACKET.json'
            timeline, timeline_evidence, timeline_receipt, timeline_packet = map(
                read_json, (timeline_path, timeline_evidence_path, timeline_receipt_path, timeline_packet_path))
            timeline_execution = read_json(timeline_execution_path)
            source_texts = {row['source_id']: row['text'].encode('utf-8') for row in timeline_packet.get('sources', [])}
            declared_outputs = {row['path']: row.get('sha256') for row in timeline_receipt.get('outputs', [])}
            exact_markers = all(
                row.get('source_id') in source_texts
                and source_texts[row['source_id']][row['source_byte_start']:row['source_byte_end_exclusive']].decode('utf-8') == row.get('literal')
                and hashlib.sha256(row.get('literal', '').encode('utf-8')).hexdigest() == row.get('literal_sha256')
                and hashlib.sha256(source_texts[row['source_id']]).hexdigest() == row.get('source_sha256')
                for row in timeline.get('markers', []))
            if (timeline.get('schema') != 'dio.incident_review.literal_time_markers.v1'
                    or timeline_evidence.get('schema') != 'dio.ai_incidentroom.literal_time_marker_execution.v1'
                    or timeline_evidence.get('marker_artifact_sha256') != hashlib.sha256(timeline_path.read_bytes()).hexdigest()
                    or timeline_evidence.get('customer_package_sha256') != hashlib.sha256(timeline_receipt_path.read_bytes()).hexdigest()
                    or timeline_evidence.get('every_marker_exact_source_bound') is not True
                    or not exact_markers
                    or timeline_evidence.get('release_authorized') is not False
                    or timeline_execution.get('release_authorized') is not False
                    or timeline_execution.get('external_effects') is not False
                    or declared_outputs.get(timeline_path.name) != hashlib.sha256(timeline_path.read_bytes()).hexdigest()):
                raise ValueError('AI IncidentRoom literal time-marker evidence is stale, unbound or crosses the release boundary')
            for artifact_path in AI_INCIDENTROOM_TIMELINE_RUN.rglob('*'):
                if artifact_path.is_file():
                    product_specific_refs.append(register(artifact_path))
            product_specific_refs.append(register(ROOT / 'scripts/run_ai_incidentroom_literal_timeline.py'))
            undated_count = len(timeline.get('undated_sources', []))
            undated_text = 'one source' if undated_count == 1 else f'{undated_count} sources'
            changes.append(f"AI IncidentRoom now surfaces {len(timeline.get('markers', []))} literal ISO date/time markers with exact source-byte spans and identifies {undated_text} without a calendar date marker. Date precision and source gaps remain visible; no event ordering, occurrence or causality is inferred.")
            limits.append('Synthetic bounded ISO extraction verifies literal source text and byte offsets only. It does not establish event occurrence, chronology completeness, impact, causation, incident severity or legal-notification duties.')
            disposition = 'CURRENT_HELD_EXECUTION_VERIFIED'
        if name == 'IncidentProof' and INCIDENTPROOF_TIMELINE_RUN.is_dir():
            marker_path = INCIDENTPROOF_TIMELINE_RUN / 'INCIDENT_LITERAL_TIME_MARKERS.json'
            evidence_path = INCIDENTPROOF_TIMELINE_RUN / 'INCIDENTPROOF_LITERAL_TIMELINE_EXECUTION_EVIDENCE.json'
            package_path = INCIDENTPROOF_TIMELINE_RUN / 'CUSTOMER_PACKAGE_RECEIPT.json'
            execution_path = INCIDENTPROOF_TIMELINE_RUN / 'CUSTOMER_EXECUTION_RECEIPT.json'
            packet_path = INCIDENTPROOF_TIMELINE_RUN / 'SOURCE_PACKET.json'
            markers, evidence, package, execution, packet = map(read_json,
                (marker_path, evidence_path, package_path, execution_path, packet_path))
            source_texts = {row['source_id']: row['text'].encode('utf-8') for row in packet.get('sources', [])}
            declared = {row['path']: row.get('sha256') for row in package.get('outputs', [])}
            exact = all(row.get('source_id') in source_texts
                        and source_texts[row['source_id']][row['source_byte_start']:row['source_byte_end_exclusive']].decode('utf-8') == row.get('literal')
                        and hashlib.sha256(row.get('literal', '').encode('utf-8')).hexdigest() == row.get('literal_sha256')
                        and hashlib.sha256(source_texts[row['source_id']]).hexdigest() == row.get('source_sha256')
                        for row in markers.get('markers', []))
            source_ids = {row.get('source_id') for row in markers.get('markers', [])}
            if (evidence.get('schema') != 'dio.incidentproof.literal_time_marker_execution.v1'
                    or markers.get('schema') != 'dio.incident_review.literal_time_markers.v1'
                    or not {'INCIDENT', 'LOG', 'RESPONSE'} <= source_ids
                    or not exact
                    or evidence.get('marker_artifact_sha256') != hashlib.sha256(marker_path.read_bytes()).hexdigest()
                    or evidence.get('customer_package_sha256') != hashlib.sha256(package_path.read_bytes()).hexdigest()
                    or evidence.get('release_authorized') is not False
                    or execution.get('release_authorized') is not False
                    or execution.get('external_effects') is not False
                    or declared.get(marker_path.name) != hashlib.sha256(marker_path.read_bytes()).hexdigest()):
                raise ValueError('IncidentProof literal time-marker evidence is stale, unbound or crosses the release boundary')
            for artifact_path in INCIDENTPROOF_TIMELINE_RUN.rglob('*'):
                if artifact_path.is_file():
                    product_specific_refs.append(register(artifact_path))
            product_specific_refs.append(register(ROOT / 'scripts/run_incidentproof_literal_timeline.py'))
            changes.append(f"IncidentProof now shows {len(markers.get('markers', []))} literal date/time markers across the incident, log and response records, preserving date-only versus offset-qualified time precision and exact source byte spans.")
            limits.append('Synthetic literal markers are source-navigation aids. They do not validate incident occurrence, sequence, impact, root cause or source truth; human review remains required.')
            disposition = 'CURRENT_HELD_EXECUTION_VERIFIED'
        if name == 'ModelProof' and MODELPROOF_SPECIALIST_REVIEW_RUN.is_dir():
            worksheet_path = MODELPROOF_SPECIALIST_REVIEW_RUN / 'SPECIALIST_REVIEW_WORKSHEET.json'
            evidence_path = MODELPROOF_SPECIALIST_REVIEW_RUN / 'MODELPROOF_SPECIALIST_REVIEW_EXECUTION_EVIDENCE.json'
            package_path = MODELPROOF_SPECIALIST_REVIEW_RUN / 'CUSTOMER_PACKAGE_RECEIPT.json'
            execution_path = MODELPROOF_SPECIALIST_REVIEW_RUN / 'CUSTOMER_EXECUTION_RECEIPT.json'
            packet_path = MODELPROOF_SPECIALIST_REVIEW_RUN / 'SOURCE_PACKET.json'
            worksheet, evidence, package, execution, packet = map(read_json,
                (worksheet_path, evidence_path, package_path, execution_path, packet_path))
            source_texts = {row['source_id']: row['text'].encode('utf-8') for row in packet.get('sources', [])}
            model_review_rows = worksheet.get('rows') or []
            exact_requirement_quotes = all(
                row.get('requirement_source_id') in source_texts
                and source_texts[row['requirement_source_id']][row['requirement_source_span'][0]:row['requirement_source_span'][1]].decode('utf-8') == row.get('requirement_quote')
                and hashlib.sha256(source_texts[row['requirement_source_id']]).hexdigest() == row.get('requirement_source_sha256')
                for row in model_review_rows)
            declared = {row['path']: row.get('sha256') for row in package.get('outputs', [])}
            if (worksheet.get('schema') != 'dio.customer_evidence.specialist_worksheet.v1'
                    or worksheet.get('product_name') != 'ModelProof'
                    or {row.get('requirement_id') for row in model_review_rows} != {'R1', 'R2', 'R3'}
                    or not exact_requirement_quotes
                    or evidence.get('schema') != 'dio.modelproof.specialist_review_execution.v1'
                    or evidence.get('worksheet_sha256') != hashlib.sha256(worksheet_path.read_bytes()).hexdigest()
                    or evidence.get('customer_package_sha256') != hashlib.sha256(package_path.read_bytes()).hexdigest()
                    or evidence.get('requirement_quotes_exact_source_bound') is not True
                    or evidence.get('source_assertions_verified') is not False
                    or worksheet.get('professional_approval') != 'NOT_GRANTED'
                    or worksheet.get('release_authorized') is not False
                    or execution.get('release_authorized') is not False
                    or execution.get('external_effects') is not False
                    or declared.get(worksheet_path.name) != hashlib.sha256(worksheet_path.read_bytes()).hexdigest()):
                raise ValueError('ModelProof specialist review evidence is stale, unbound or crosses the review boundary')
            for artifact_path in MODELPROOF_SPECIALIST_REVIEW_RUN.rglob('*'):
                if artifact_path.is_file():
                    product_specific_refs.append(register(artifact_path))
            product_specific_refs.append(register(ROOT / 'scripts/run_modelproof_specialist_review.py'))
            changes.append('ModelProof now provides a source-bound reviewer queue for each supplied model-use, evaluation-coverage and change-control requirement. The worksheet retains the reported language exclusions, missing subgroup analysis and post-change regression/rollback/approval gap as unverified items for a model reviewer.')
            limits.append('The synthetic worksheet organizes customer claims and review questions only. It does not assess model quality, subgroup fairness, regression adequacy, rollback readiness, source truth or approval.')
            disposition = 'CURRENT_HELD_EXECUTION_VERIFIED'
        if name == 'QualityProof' and QUALITYPROOF_CAPA_TRACKER_RUN.is_dir():
            tracker_path = QUALITYPROOF_CAPA_TRACKER_RUN / 'QUALITYPROOF_CAPA_REVIEW_TRACKER.json'
            csv_path = QUALITYPROOF_CAPA_TRACKER_RUN / 'QUALITYPROOF_CAPA_REVIEW_TRACKER.csv'
            evidence_path = QUALITYPROOF_CAPA_TRACKER_RUN / 'QUALITYPROOF_CAPA_TRACKER_EXECUTION_EVIDENCE.json'
            package_path = QUALITYPROOF_CAPA_TRACKER_RUN / 'CUSTOMER_PACKAGE_RECEIPT.json'
            execution_path = QUALITYPROOF_CAPA_TRACKER_RUN / 'CUSTOMER_EXECUTION_RECEIPT.json'
            packet_path = QUALITYPROOF_CAPA_TRACKER_RUN / 'SOURCE_PACKET.json'
            tracker, evidence, package, execution, packet = map(read_json,
                (tracker_path, evidence_path, package_path, execution_path, packet_path))
            capa_items = tracker.get('items') or []
            capa = capa_items[0] if len(capa_items) == 1 else {}
            source_texts = {row['source_id']: row['text'].encode('utf-8') for row in packet.get('sources', [])}
            anchors = [capa.get('source_reported_finding') or {}, capa.get('closure_evidence_issue') or {},
                       *(capa.get('assigned_date_candidates') or []), capa.get('planned_effectiveness_date') or {},
                       capa.get('review_note_date') or {}]
            exact_capa_anchors = all(
                row.get('source_id') in source_texts
                and source_texts[row['source_id']][row['source_byte_start']:row['source_byte_end_exclusive']].decode('utf-8') == row.get('literal', row.get('quote'))
                and hashlib.sha256(row.get('literal', row.get('quote', '')).encode('utf-8')).hexdigest() == row.get('literal_sha256')
                and hashlib.sha256(source_texts[row['source_id']]).hexdigest() == row.get('source_sha256')
                for row in anchors)
            declared = {row['path']: row.get('sha256') for row in package.get('outputs', [])}
            blank_fields = ('verified_owner', 'verified_action_due_date', 'closure_evidence_reference',
                            'effectiveness_check_result', 'reviewer_decision', 'reviewer_name',
                            'reviewed_at_iso8601', 'reviewer_rationale')
            if (tracker.get('schema') != 'dio.qualityproof.capa_review_tracker.v1'
                    or capa.get('capa_id') != 'CAPA-204'
                    or capa.get('closure_evidence_state') != 'SOURCE_REPORTS_RECORD_NOT_FOUND'
                    or not exact_capa_anchors
                    or any(capa.get('review_fields', {}).get(field) for field in blank_fields)
                    or evidence.get('schema') != 'dio.qualityproof.capa_tracker_execution.v1'
                    or evidence.get('tracker_sha256') != hashlib.sha256(tracker_path.read_bytes()).hexdigest()
                    or evidence.get('csv_sha256') != hashlib.sha256(csv_path.read_bytes()).hexdigest()
                    or evidence.get('customer_package_sha256') != hashlib.sha256(package_path.read_bytes()).hexdigest()
                    or evidence.get('all_source_anchors_exact') is not True
                    or tracker.get('professional_approval') != 'NOT_GRANTED'
                    or tracker.get('release_authorized') is not False
                    or execution.get('release_authorized') is not False
                    or execution.get('external_effects') is not False
                    or declared.get(tracker_path.name) != hashlib.sha256(tracker_path.read_bytes()).hexdigest()
                    or declared.get(csv_path.name) != hashlib.sha256(csv_path.read_bytes()).hexdigest()):
                raise ValueError('QualityProof CAPA tracker is stale, unbound or crosses the reviewer boundary')
            for artifact_path in QUALITYPROOF_CAPA_TRACKER_RUN.rglob('*'):
                if artifact_path.is_file():
                    product_specific_refs.append(register(artifact_path))
            product_specific_refs.append(register(ROOT / 'products/qualityproof_capa_tracker.py'))
            product_specific_refs.append(register(ROOT / 'scripts/run_qualityproof_capa_tracker.py'))
            changes.append('QualityProof now provides a source-bound CAPA-204 tracker connecting the reported owner-assignment and planned-effectiveness dates to the later source-reported missing closure record. An editable CSV captures verified owner, closure evidence, effectiveness result and reviewer decision; those fields remain blank pending review.')
            limits.append('The synthetic tracker preserves customer-reported facts and dates only. Its date comparison does not establish overdue status, CAPA effectiveness, adequacy, closure or source truth.')
            disposition = 'CURRENT_HELD_EXECUTION_VERIFIED'
        if name == 'VendorProof' and VENDORPROOF_DOCUMENT_REQUEST_RUN.is_dir():
            register_path = VENDORPROOF_DOCUMENT_REQUEST_RUN / 'VENDORPROOF_DOCUMENT_REQUEST_REGISTER.json'
            csv_path = VENDORPROOF_DOCUMENT_REQUEST_RUN / 'VENDORPROOF_DOCUMENT_REQUEST_REGISTER.csv'
            evidence_path = VENDORPROOF_DOCUMENT_REQUEST_RUN / 'VENDORPROOF_DOCUMENT_REQUEST_EXECUTION_EVIDENCE.json'
            package_path = VENDORPROOF_DOCUMENT_REQUEST_RUN / 'CUSTOMER_PACKAGE_RECEIPT.json'
            execution_path = VENDORPROOF_DOCUMENT_REQUEST_RUN / 'CUSTOMER_EXECUTION_RECEIPT.json'
            packet_path = VENDORPROOF_DOCUMENT_REQUEST_RUN / 'SOURCE_PACKET.json'
            request_register, evidence, package, execution, packet = map(read_json,
                (register_path, evidence_path, package_path, execution_path, packet_path))
            source_texts = {row['source_id']: row['text'].encode('utf-8') for row in packet.get('sources', [])}
            requests = request_register.get('requests') or []
            exact_anchors = all(
                anchor.get('source_id') in source_texts
                and source_texts[anchor['source_id']][anchor['source_byte_start']:anchor['source_byte_end_exclusive']].decode('utf-8') == anchor.get('quote', anchor.get('literal'))
                and hashlib.sha256(source_texts[anchor['source_id']]).hexdigest() == anchor.get('source_sha256')
                for request in requests for anchor in request.get('source_anchors', []) + request.get('date_candidates', []))
            declared = {row['path']: row.get('sha256') for row in package.get('outputs', [])}
            if (request_register.get('schema') != 'dio.vendorproof.document_request_register.v1'
                    or {row.get('request_id') for row in requests} != {'VREQ-DPA', 'VREQ-SECURITY'}
                    or not exact_anchors
                    or any(any(row.get('request_fields', {}).values()) for row in requests)
                    or evidence.get('schema') != 'dio.vendorproof.document_request_execution.v1'
                    or evidence.get('register_sha256') != hashlib.sha256(register_path.read_bytes()).hexdigest()
                    or evidence.get('csv_sha256') != hashlib.sha256(csv_path.read_bytes()).hexdigest()
                    or evidence.get('customer_package_sha256') != hashlib.sha256(package_path.read_bytes()).hexdigest()
                    or evidence.get('all_source_anchors_exact') is not True
                    or evidence.get('source_authenticity_verified') is not False
                    or request_register.get('professional_approval') != 'NOT_GRANTED'
                    or request_register.get('release_authorized') is not False
                    or execution.get('release_authorized') is not False
                    or execution.get('external_effects') is not False
                    or declared.get(register_path.name) != hashlib.sha256(register_path.read_bytes()).hexdigest()
                    or declared.get(csv_path.name) != hashlib.sha256(csv_path.read_bytes()).hexdigest()):
                raise ValueError('VendorProof document requests are stale, unbound or cross the procurement review boundary')
            for artifact_path in VENDORPROOF_DOCUMENT_REQUEST_RUN.rglob('*'):
                if artifact_path.is_file():
                    product_specific_refs.append(register(artifact_path))
            product_specific_refs.append(register(ROOT / 'products/vendorproof_document_requests.py'))
            product_specific_refs.append(register(ROOT / 'scripts/run_vendorproof_document_requests.py'))
            changes.append('VendorProof now provides source-bound request rows for the executed data-processing addendum and annual security review. Procurement can record request ownership, received document references and hashes, and human authenticity review; source-reported states and the reported review date remain unverified.')
            limits.append('The synthetic register organizes document follow-up only. It establishes no supplier identity, document authenticity, security adequacy, legal sufficiency or compliance conclusion.')
            disposition = 'CURRENT_HELD_EXECUTION_VERIFIED'
        if name == 'AuditProof' and AUDITPROOF_EXCEPTION_TRACKER_RUN.is_dir():
            tracker_path = AUDITPROOF_EXCEPTION_TRACKER_RUN / 'AUDITPROOF_ACCESS_REVIEW_EXCEPTION_TRACKER.json'
            csv_path = AUDITPROOF_EXCEPTION_TRACKER_RUN / 'AUDITPROOF_ACCESS_REVIEW_EXCEPTION_TRACKER.csv'
            evidence_path = AUDITPROOF_EXCEPTION_TRACKER_RUN / 'AUDITPROOF_EXCEPTION_TRACKER_EXECUTION_EVIDENCE.json'
            package_path = AUDITPROOF_EXCEPTION_TRACKER_RUN / 'CUSTOMER_PACKAGE_RECEIPT.json'
            execution_path = AUDITPROOF_EXCEPTION_TRACKER_RUN / 'CUSTOMER_EXECUTION_RECEIPT.json'
            packet_path = AUDITPROOF_EXCEPTION_TRACKER_RUN / 'SOURCE_PACKET.json'
            tracker, evidence, package, execution, packet = map(read_json,
                (tracker_path, evidence_path, package_path, execution_path, packet_path))
            source_texts = {row['source_id']: row['text'].encode('utf-8') for row in packet.get('sources', [])}
            anchors = [tracker.get('control_requirement') or {}, tracker.get('review_sample') or {},
                       tracker.get('exception_group') or {}, *(tracker.get('reported_counts', {}).get('count_anchors') or [])]
            exact_anchors = all(
                row.get('source_id') in source_texts
                and source_texts[row['source_id']][row['source_byte_start']:row['source_byte_end_exclusive']].decode('utf-8') == row.get('quote', row.get('literal', row.get('source_quote', row.get('issue_quote'))))
                and hashlib.sha256(source_texts[row['source_id']]).hexdigest() == row.get('source_sha256')
                for row in anchors)
            counts = tracker.get('reported_counts') or {}
            declared = {row['path']: row.get('sha256') for row in package.get('outputs', [])}
            if (tracker.get('schema') != 'dio.auditproof.access_review_exception_tracker.v1'
                    or counts.get('total_listed') != 42
                    or counts.get('marked_reviewed') != 39
                    or counts.get('no_outcome_reported') != 3
                    or counts.get('arithmetic_reconciles') is not True
                    or not exact_anchors
                    or tracker.get('exception_group', {}).get('fabricated_account_rows_created') is not False
                    or any(tracker.get('review_fields', {}).values())
                    or evidence.get('schema') != 'dio.auditproof.exception_tracker_execution.v1'
                    or evidence.get('tracker_sha256') != hashlib.sha256(tracker_path.read_bytes()).hexdigest()
                    or evidence.get('csv_sha256') != hashlib.sha256(csv_path.read_bytes()).hexdigest()
                    or evidence.get('customer_package_sha256') != hashlib.sha256(package_path.read_bytes()).hexdigest()
                    or evidence.get('all_source_anchors_exact') is not True
                    or evidence.get('account_ids_invented') is not False
                    or tracker.get('professional_approval') != 'NOT_GRANTED'
                    or tracker.get('release_authorized') is not False
                    or execution.get('release_authorized') is not False
                    or execution.get('external_effects') is not False
                    or declared.get(tracker_path.name) != hashlib.sha256(tracker_path.read_bytes()).hexdigest()
                    or declared.get(csv_path.name) != hashlib.sha256(csv_path.read_bytes()).hexdigest()):
                raise ValueError('AuditProof access-review tracker is stale, unbound or crosses the audit boundary')
            for artifact_path in AUDITPROOF_EXCEPTION_TRACKER_RUN.rglob('*'):
                if artifact_path.is_file():
                    product_specific_refs.append(register(artifact_path))
            product_specific_refs.append(register(ROOT / 'products/auditproof_exception_tracker.py'))
            product_specific_refs.append(register(ROOT / 'scripts/run_auditproof_exception_tracker.py'))
            changes.append('AuditProof now turns the reported 42/39/3 access-review counts into one source-bound auditor follow-up row; the arithmetic reconciles, but the three account identities are absent from the excerpt. An editable tracker requests the original worksheet, individual outcomes and dated closure evidence without fabricating account rows.')
            limits.append('Synthetic aggregate arithmetic does not verify account-level outcomes, closure evidence or control effectiveness. Source truth and audit conclusions remain for a qualified auditor.')
            disposition = 'CURRENT_HELD_EXECUTION_VERIFIED'
        if name in OBLIGATION_FAMILY_SOURCE_REVIEWS and OBLIGATION_FAMILY_SOURCE_REVIEWS[name][1].is_dir():
            example, review_root = OBLIGATION_FAMILY_SOURCE_REVIEWS[name]
            package_path = review_root / 'CUSTOMER_OBLIGATION_FAMILY_RECEIPT.json'
            execution_path = review_root / 'CUSTOMER_EXECUTION_RECEIPT.json'
            evidence_path = review_root / f'{example.upper()}_SOURCE_ALIGNMENT_EVIDENCE.json'
            pack_path = review_root / 'evidence_pack/EVIDENCE_PACK.json'
            source_path = review_root / 'customer_sources/governing_instrument.txt'
            example_path = ROOT / f'config/customer_products/examples/{example}.json'
            package, execution, evidence, pack, packet = map(read_json,
                (package_path, execution_path, evidence_path, pack_path, example_path))
            source_bytes = source_path.read_bytes()
            provenance = pack.get('provenance_manifest') or {}
            clause_sources = provenance.get('source_clause_sources') or []
            evidence_sources = provenance.get('evidence_input_sources') or []
            obligations = pack.get('requirement_or_obligation_ledger') or []
            evidence_maps = pack.get('evidence_map') or []
            locator_by_id = {row.get('obligation_id'): (row.get('source') or {}).get('locator') for row in obligations}
            actual_relations = Counter((locator_by_id.get(row.get('obligation_id')), row.get('relation')) for row in evidence_maps)
            expected_relations = Counter((target, row.get('relation'))
                                         for row in packet.get('evidence') or []
                                         for target in row.get('target_locators') or [])
            valid_clauses = len(clause_sources) == len(packet.get('obligations') or []) and all(
                row.get('source_match_state') == 'UNIQUE_EXACT_MATCH'
                and source_bytes[row.get('source_byte_start'):row.get('source_byte_end_exclusive')].decode('utf-8') == row.get('text')
                for row in clause_sources)
            valid_evidence_bytes = len(evidence_sources) == len(packet.get('evidence') or [])
            for row in evidence_sources:
                evidence_file = review_root / str(row.get('source_file_ref') or '')
                if not evidence_file.is_file():
                    valid_evidence_bytes = False
                    continue
                actual_sha = hashlib.sha256(evidence_file.read_bytes()).hexdigest()
                valid_evidence_bytes = valid_evidence_bytes and row.get('source_byte_start') == 0 \
                    and row.get('source_byte_end_exclusive') == evidence_file.stat().st_size \
                    and row.get('source_file_sha256') == actual_sha and row.get('source_row_sha256') == actual_sha \
                    and row.get('source_statement_sha256') == actual_sha
            if (package.get('product_name') != name
                    or package.get('source_sha256') != hashlib.sha256(source_bytes).hexdigest()
                    or evidence.get('product') != name
                    or evidence.get('customer_package_receipt_sha256') != hashlib.sha256(package_path.read_bytes()).hexdigest()
                    or evidence.get('evidence_pack_sha256') != hashlib.sha256(pack_path.read_bytes()).hexdigest()
                    or not valid_clauses or not valid_evidence_bytes or actual_relations != expected_relations
                    or evidence.get('all_items_need_human_review') is not True
                    or package.get('external_release') != 'REFUSE' or package.get('authority_created') is not False
                    or execution.get('external_effects') is not False
                    or not all((review_root / f'evidence_pack/EVIDENCE_PACK.{ext}').is_file() for ext in ('pdf', 'docx', 'html'))):
                raise ValueError(f'{name} source clauses or applicant-evidence relationships are stale or misaligned')
            for artifact_row in package.get('artifacts') or []:
                artifact_path = review_root / artifact_row['path']
                if not artifact_path.is_file() or hashlib.sha256(artifact_path.read_bytes()).hexdigest() != artifact_row.get('sha256'):
                    raise ValueError(f"{name} customer package artifact hash mismatch: {artifact_row.get('path')}")
            for artifact_path in review_root.rglob('*'):
                if artifact_path.is_file():
                    product_specific_refs.append(register(artifact_path))
            product_specific_refs.extend([register(example_path), register(ROOT / 'scripts/run_obligation_family_source_review_batch.py'),
                                          register(ROOT / 'products/obligationfamily/customer_runner.py'),
                                          register(ROOT / 'products/obligationfamily/runner.py')])
            changes.append(f'{name} now separates {len(obligations)} instrument conditions from {len(evidence_maps)} applicant-record mappings. Clause text and evidence attachments have exact byte/hash provenance, and the source-declared supports/contradictions match the rendered evidence map; every obligation remains NEEDS_REVIEW.')
            limits = ['These are synthetic, unverified review examples. No award, permit, policy approval, tender submission, legal determination or fulfilment is established; professional review and external release remain unavailable.']
            disposition = 'CURRENT_HELD_EXECUTION_VERIFIED'
        if name == 'DonorProof' and DONORPROOF_EXPENDITURE_TRACKER_RUN.is_dir():
            tracker_path = DONORPROOF_EXPENDITURE_TRACKER_RUN / 'DONORPROOF_EXPENDITURE_RECONCILIATION_REQUEST.json'
            csv_path = DONORPROOF_EXPENDITURE_TRACKER_RUN / 'DONORPROOF_EXPENDITURE_RECONCILIATION_REQUEST.csv'
            evidence_path = DONORPROOF_EXPENDITURE_TRACKER_RUN / 'DONORPROOF_EXPENDITURE_TRACKER_EXECUTION_EVIDENCE.json'
            package_path = DONORPROOF_EXPENDITURE_TRACKER_RUN / 'CUSTOMER_PACKAGE_RECEIPT.json'
            execution_path = DONORPROOF_EXPENDITURE_TRACKER_RUN / 'CUSTOMER_EXECUTION_RECEIPT.json'
            packet_path = DONORPROOF_EXPENDITURE_TRACKER_RUN / 'SOURCE_PACKET.json'
            tracker, evidence, package, execution, packet = map(read_json,
                (tracker_path, evidence_path, package_path, execution_path, packet_path))
            donor_requests = tracker.get('requests') or []
            request = donor_requests[0] if len(donor_requests) == 1 else {}
            source_texts = {row['source_id']: row['text'].encode('utf-8') for row in packet.get('sources', [])}
            donor_anchors = list(request.get('source_anchors') or []) + [request.get('restricted_use_wording') or {},
                           request.get('reported_expenditure') or {}, request.get('missing_invoice_count_anchor') or {}]
            exact_donor_anchors = all(
                row.get('source_id') in source_texts
                and source_texts[row['source_id']][row['source_byte_start']:row['source_byte_end_exclusive']].decode('utf-8') == row.get('quote', row.get('literal'))
                and hashlib.sha256(source_texts[row['source_id']]).hexdigest() == row.get('source_sha256')
                for row in donor_anchors)
            declared = {row['path']: row.get('sha256') for row in package.get('outputs', [])}
            if (tracker.get('schema') != 'dio.donorproof.expenditure_reconciliation_request.v1'
                    or request.get('reported_expenditure', {}).get('amount') != 145000
                    or request.get('reported_expenditure', {}).get('currency') != 'ZAR'
                    or request.get('reported_expenditure', {}).get('period') != 'Q3 2026'
                    or request.get('reported_invoice_image_count') != 3
                    or request.get('invoice_level_amounts_supplied') is not False
                    or request.get('reconciliation_state') != 'NOT_COMPUTABLE_MISSING_INVOICE_VALUES'
                    or not exact_donor_anchors
                    or any(request.get('review_fields', {}).values())
                    or evidence.get('schema') != 'dio.donorproof.expenditure_tracker_execution.v1'
                    or evidence.get('tracker_sha256') != hashlib.sha256(tracker_path.read_bytes()).hexdigest()
                    or evidence.get('csv_sha256') != hashlib.sha256(csv_path.read_bytes()).hexdigest()
                    or evidence.get('customer_package_sha256') != hashlib.sha256(package_path.read_bytes()).hexdigest()
                    or evidence.get('all_source_anchors_exact') is not True
                    or evidence.get('eligibility_or_compliance_determination') is not False
                    or tracker.get('professional_approval') != 'NOT_GRANTED'
                    or tracker.get('release_authorized') is not False
                    or execution.get('release_authorized') is not False
                    or execution.get('external_effects') is not False
                    or declared.get(tracker_path.name) != hashlib.sha256(tracker_path.read_bytes()).hexdigest()
                    or declared.get(csv_path.name) != hashlib.sha256(csv_path.read_bytes()).hexdigest()):
                raise ValueError('DonorProof expenditure tracker is stale, unbound or crosses the donor review boundary')
            for artifact_path in DONORPROOF_EXPENDITURE_TRACKER_RUN.rglob('*'):
                if artifact_path.is_file():
                    product_specific_refs.append(register(artifact_path))
            product_specific_refs.append(register(ROOT / 'products/donorproof_expenditure_tracker.py'))
            product_specific_refs.append(register(ROOT / 'scripts/run_donorproof_expenditure_tracker.py'))
            changes.append('DonorProof now ties the Q3 ZAR 145,000 expenditure report to the grant restriction and the source-reported three missing invoice images. Its editable request register asks for itemized invoices and payment references, and marks reconciliation uncomputable until invoice-level values are supplied.')
            limits.append('The synthetic packet does not authenticate the grant agreement, ledger or invoices. No expense eligibility, grant compliance or donor reporting conclusion is produced.')
            disposition = 'CURRENT_HELD_EXECUTION_VERIFIED'
        if name == 'ImpactProof' and IMPACTPROOF_FOLLOWUP_REQUEST_RUN.is_dir():
            request_path = IMPACTPROOF_FOLLOWUP_REQUEST_RUN / 'IMPACTPROOF_FOLLOWUP_EVIDENCE_REQUEST.json'
            csv_path = IMPACTPROOF_FOLLOWUP_REQUEST_RUN / 'IMPACTPROOF_FOLLOWUP_EVIDENCE_REQUEST.csv'
            evidence_path = IMPACTPROOF_FOLLOWUP_REQUEST_RUN / 'IMPACTPROOF_FOLLOWUP_REQUEST_EXECUTION_EVIDENCE.json'
            package_path = IMPACTPROOF_FOLLOWUP_REQUEST_RUN / 'CUSTOMER_PACKAGE_RECEIPT.json'
            execution_path = IMPACTPROOF_FOLLOWUP_REQUEST_RUN / 'CUSTOMER_EXECUTION_RECEIPT.json'
            packet_path = IMPACTPROOF_FOLLOWUP_REQUEST_RUN / 'SOURCE_PACKET.json'
            request_register, evidence, package, execution, packet = map(read_json,
                (request_path, evidence_path, package_path, execution_path, packet_path))
            cohort = request_register.get('cohort_request') or {}
            impact_anchors = [cohort.get('outcome_definition') or {}, cohort.get('reported_placement') or {}, cohort.get('followup_gap') or {}]
            source_texts = {row['source_id']: row['text'].encode('utf-8') for row in packet.get('sources', [])}
            exact_impact_anchors = all(
                row.get('source_id') in source_texts
                and source_texts[row['source_id']][row['source_byte_start']:row['source_byte_end_exclusive']].decode('utf-8') == row.get('quote')
                and hashlib.sha256(source_texts[row['source_id']]).hexdigest() == row.get('source_sha256')
                for row in impact_anchors)
            declared = {row['path']: row.get('sha256') for row in package.get('outputs', [])}
            if (request_register.get('schema') != 'dio.impactproof.followup_evidence_request.v1'
                    or cohort.get('reported_cohort_size') != 27
                    or cohort.get('reported_cohort_period') != '2026 Q3'
                    or cohort.get('required_followup_duration_months') != 6
                    or cohort.get('followup_records_state') != 'SOURCE_REPORTS_NO_RECORDS_INCLUDED'
                    or cohort.get('sustained_outcome_count') is not None
                    or not exact_impact_anchors
                    or any(cohort.get('request_fields', {}).values())
                    or evidence.get('schema') != 'dio.impactproof.followup_request_execution.v1'
                    or evidence.get('request_sha256') != hashlib.sha256(request_path.read_bytes()).hexdigest()
                    or evidence.get('csv_sha256') != hashlib.sha256(csv_path.read_bytes()).hexdigest()
                    or evidence.get('customer_package_sha256') != hashlib.sha256(package_path.read_bytes()).hexdigest()
                    or evidence.get('all_source_anchors_exact') is not True
                    or evidence.get('sustained_outcome_count_calculated') is not False
                    or request_register.get('professional_approval') != 'NOT_GRANTED'
                    or request_register.get('release_authorized') is not False
                    or execution.get('release_authorized') is not False
                    or execution.get('external_effects') is not False
                    or declared.get(request_path.name) != hashlib.sha256(request_path.read_bytes()).hexdigest()
                    or declared.get(csv_path.name) != hashlib.sha256(csv_path.read_bytes()).hexdigest()):
                raise ValueError('ImpactProof follow-up evidence request is stale, unbound or crosses the evaluation boundary')
            for artifact_path in IMPACTPROOF_FOLLOWUP_REQUEST_RUN.rglob('*'):
                if artifact_path.is_file():
                    product_specific_refs.append(register(artifact_path))
            product_specific_refs.append(register(ROOT / 'products/impactproof_followup_request.py'))
            product_specific_refs.append(register(ROOT / 'scripts/run_impactproof_followup_request.py'))
            changes.append('ImpactProof now turns the reported 27-person Q3 placement cohort and the six-month outcome definition into a source-bound follow-up request. The register asks for participant-level start and follow-up records while leaving the sustained-outcome count uncalculated because no follow-up records were supplied.')
            limits.append('The synthetic request does not establish placement truth, six-month employment continuity, participant-level outcomes or programme impact; evaluator review remains required.')
            disposition = 'CURRENT_HELD_EXECUTION_VERIFIED'
        if name == 'ProgrammeProof' and PROGRAMMEPROOF_ATTENDANCE_TRACKER_RUN.is_dir():
            tracker_path = PROGRAMMEPROOF_ATTENDANCE_TRACKER_RUN / 'PROGRAMMEPROOF_ATTENDANCE_EVIDENCE_TRACKER.json'
            csv_path = PROGRAMMEPROOF_ATTENDANCE_TRACKER_RUN / 'PROGRAMMEPROOF_ATTENDANCE_EVIDENCE_TRACKER.csv'
            evidence_path = PROGRAMMEPROOF_ATTENDANCE_TRACKER_RUN / 'PROGRAMMEPROOF_ATTENDANCE_TRACKER_EXECUTION_EVIDENCE.json'
            package_path = PROGRAMMEPROOF_ATTENDANCE_TRACKER_RUN / 'CUSTOMER_PACKAGE_RECEIPT.json'
            execution_path = PROGRAMMEPROOF_ATTENDANCE_TRACKER_RUN / 'CUSTOMER_EXECUTION_RECEIPT.json'
            packet_path = PROGRAMMEPROOF_ATTENDANCE_TRACKER_RUN / 'SOURCE_PACKET.json'
            tracker, evidence, package, execution, packet = map(read_json,
                (tracker_path, evidence_path, package_path, execution_path, packet_path))
            programme_review = tracker.get('review') or {}
            programme_anchors = [programme_review.get('plan_source') or {}, programme_review.get('delivery_log_source') or {},
                                 programme_review.get('exception_source') or {}, programme_review.get('missing_count_anchor') or {}]
            programme_sources = {row['source_id']: row['text'].encode('utf-8') for row in packet.get('sources', [])}
            exact_programme_anchors = all(
                row.get('source_id') in programme_sources
                and programme_sources[row['source_id']][row['source_byte_start']:row['source_byte_end_exclusive']].decode('utf-8') == row.get('quote', row.get('literal'))
                and hashlib.sha256(programme_sources[row['source_id']]).hexdigest() == row.get('source_sha256')
                for row in programme_anchors)
            declared = {row['path']: row.get('sha256') for row in package.get('outputs', [])}
            if (tracker.get('schema') != 'dio.programmeproof.attendance_evidence_tracker.v1'
                    or programme_review.get('reported_sessions') != 18
                    or programme_review.get('reported_site_count') != 5
                    or programme_review.get('sessions_with_sheets_reported') != 15
                    or programme_review.get('sessions_without_sheets_reported') != 3
                    or programme_review.get('count_arithmetic_reconciles') is not True
                    or programme_review.get('participant_reach_count') is not None
                    or programme_review.get('fabricated_session_rows_created') is not False
                    or not exact_programme_anchors
                    or any((tracker.get('request') or {}).get('review_fields', {}).values())
                    or evidence.get('schema') != 'dio.programmeproof.attendance_tracker_execution.v1'
                    or evidence.get('tracker_sha256') != digest_file(tracker_path)
                    or evidence.get('csv_sha256') != digest_file(csv_path)
                    or evidence.get('customer_package_sha256') != digest_file(package_path)
                    or evidence.get('all_source_anchors_exact') is not True
                    or evidence.get('participant_reach_calculated') is not False
                    or tracker.get('professional_approval') != 'NOT_GRANTED'
                    or tracker.get('release_authorized') is not False
                    or execution.get('release_authorized') is not False
                    or execution.get('external_effects') is not False
                    or declared.get(tracker_path.name) != digest_file(tracker_path)
                    or declared.get(csv_path.name) != digest_file(csv_path)):
                raise ValueError('ProgrammeProof attendance tracker is stale, unbound or crosses the reach-reporting boundary')
            for artifact_path in PROGRAMMEPROOF_ATTENDANCE_TRACKER_RUN.rglob('*'):
                if artifact_path.is_file():
                    product_specific_refs.append(register(artifact_path))
            product_specific_refs.append(register(ROOT / 'products/programmeproof_attendance_tracker.py'))
            product_specific_refs.append(register(ROOT / 'scripts/run_programmeproof_attendance_tracker.py'))
            changes.append('ProgrammeProof now gives reviewers an editable attendance-sheet follow-up tied to exact plan, delivery-log and exception source bytes. The reported 18 sessions reconcile arithmetically to 15 sheets supplied plus three missing, while the absent session identities and participant reach remain unresolved.')
            limits.append('The synthetic packet verifies source anchoring and aggregate arithmetic only. It does not authenticate session delivery, site coverage, attendance or participant reach; programme evidence review remains required.')
            disposition = 'CURRENT_HELD_EXECUTION_VERIFIED'
        if name == 'POPIA Readiness' and POPIA_PROCESSING_ACTIVITY_RUN.is_dir():
            popia_package_path = POPIA_PROCESSING_ACTIVITY_RUN / 'CUSTOMER_PACKAGE_RECEIPT.json'
            popia_inventory_path = POPIA_PROCESSING_ACTIVITY_RUN / 'CUSTOMER_PROCESSING_ACTIVITY_INVENTORY.json'
            popia_validation_path = POPIA_PROCESSING_ACTIVITY_RUN / 'POPIA_PROCESSING_INVENTORY_VALIDATION.json'
            if all(path.is_file() for path in (popia_package_path, popia_inventory_path, popia_validation_path)):
                popia_package = read_json(popia_package_path)
                popia_inventory = read_json(popia_inventory_path)
                popia_validation = read_json(popia_validation_path)
                declared_outputs = {row['path']: row.get('sha256') for row in popia_package.get('outputs') or []}
                inventory_row = next((row for row in popia_inventory.get('activities', [])), {})
                if (popia_validation.get('schema') != 'dio.popia.processing_inventory_validation.v1'
                        or popia_validation.get('status') != 'PASS'
                        or popia_validation.get('failed_count') != 0
                        or popia_validation.get('check_count') != popia_validation.get('passed_count')
                        or popia_inventory.get('schema') != 'dio.popia.customer_processing_activity_inventory.v1'
                        or popia_inventory.get('compliance_determination') is not False
                        or popia_inventory.get('human_review_required') is not True
                        or popia_package.get('professional_approval') != 'NOT_GRANTED'
                        or popia_package.get('authority_created') is not False
                        or declared_outputs.get(popia_inventory_path.name) != digest_file(popia_inventory_path)
                        or declared_outputs.get(popia_validation_path.name) != digest_file(popia_validation_path)
                        or popia_package.get('customer_processing_inventory_validation', {}).get('status') != 'PASS'):
                    raise ValueError('POPIA Readiness processing inventory evidence is stale or crossed an advice/release boundary')
                for output_path, sha256 in declared_outputs.items():
                    path = POPIA_PROCESSING_ACTIVITY_RUN / output_path
                    if path.is_file():
                        product_specific_refs.append(register(path, sha256))
                product_specific_refs.append(register(popia_package_path))
                captured_fields = sum(bool(row.get('source_anchor')) for row in inventory_row.get('fields', []))
                missing_fields = sum(row.get('customer_source_state') == 'NOT_SUPPLIED_IN_PACKET' for row in inventory_row.get('fields', []))
                changes.append(f"The POPIA Readiness packet now produces a thirteen-field customer-reported processing inventory, with {captured_fields} fields tied to exact source quotes and {missing_fields} marked not supplied in the packet. Its post-render source-byte validator passed {popia_validation.get('passed_count')}/{popia_validation.get('check_count')} checks; omissions are not treated as proof of absent processing or controls.")
                limits.append('The inventory is synthetic, source-bound customer input only. It does not determine POPIA applicability, legal interpretation, compliance, control adequacy, completeness or customer truth; privacy-professional review remains required.')
                disposition = 'CURRENT_HELD_EXECUTION_VERIFIED'
        if name == 'Launch Studio' and LAUNCH_STUDIO_VISUAL_REVIEW.is_file():
            visual_review = read_json(LAUNCH_STUDIO_VISUAL_REVIEW)
            if (visual_review.get('asset_count') != 9 or visual_review.get('passed_count') != 9
                    or visual_review.get('failed_count') != 0 or visual_review.get('publication_authorized') is not False
                    or any(row.get('visual_disposition') != 'PASS_NO_TEXT_OR_CTA_COLLISION' for row in visual_review.get('assets', []))):
                raise ValueError('Launch Studio visual review is incomplete or contains a layout failure')
            product_specific_refs.append(register(LAUNCH_STUDIO_VISUAL_REVIEW))
            changes.append('The current baseline, adversarial and unseen launch assets were regenerated after a visible headline/CTA collision, then all 9 channel creatives passed a fresh layout review; publication remains held.')
            limits.append('Visual review covers layout only for these 9 synthetic assets. It does not establish copy truth, brand rights, destination accuracy, customer acceptance or publication authorization.')
        if name == 'Launch Studio' and LAUNCH_STUDIO_RENDERED_SOURCE_BINDING.is_dir():
            launch_package_path = LAUNCH_STUDIO_RENDERED_SOURCE_BINDING / 'package_manifest.json'
            launch_source_binding_path = LAUNCH_STUDIO_RENDERED_SOURCE_BINDING / 'review/SOURCE_BINDING_RECEIPT.json'
            if launch_package_path.is_file() and launch_source_binding_path.is_file():
                launch_package = read_json(launch_package_path)
                launch_binding = read_json(launch_source_binding_path)
                if (launch_binding.get('schema') != 'dio.customer_launch_source_binding_receipt.v1'
                        or launch_binding.get('status') != 'PASS'
                        or launch_binding.get('check_count') != launch_binding.get('passed_count')
                        or launch_binding.get('failed_count') != 0
                        or launch_binding.get('release_authorized') is not False
                        or launch_binding.get('publication_performed') is not False
                        or launch_package.get('source_binding_receipt', {}).get('status') != 'PASS'
                        or launch_package.get('qa', {}).get('source_binding_passed') is not True
                        or launch_package.get('release', {}).get('published') is not False
                        or launch_package.get('release', {}).get('spend_enabled') is not False):
                    raise ValueError('Launch Studio rendered source-binding receipt is stale or crossed a release boundary')
                product_specific_refs.extend([register(launch_package_path), register(launch_source_binding_path)])
                for path in (LAUNCH_STUDIO_RENDERED_SOURCE_BINDING / 'review/source_semantic_manifest.json',
                             LAUNCH_STUDIO_RENDERED_SOURCE_BINDING / 'channel_copy.json',
                             LAUNCH_STUDIO_RENDERED_SOURCE_BINDING / 'landing.html',
                             LAUNCH_STUDIO_RENDERED_SOURCE_BINDING / 'launch_schedule.json'):
                    if path.is_file():
                        product_specific_refs.append(register(path))
                changes.append(f"A rendered synthetic launch kit now reopens its delivered copy, poster files, landing page, CTA and schedule for independent source-binding checks; {launch_binding.get('passed_count')}/{launch_binding.get('check_count')} checks passed. Publication and spend remain disabled, and visual, brand-rights and customer-release review are pending.")
                limits.append('Source-binding proves rendered text and files match supplied source anchors; it does not verify source truth, image rights, visual quality, platform policy, customer approval, publication or campaign performance.')
                disposition = 'CURRENT_HELD_EXECUTION_VERIFIED'
        if name == 'Launch Studio' and LAUNCH_STUDIO_CUSTOMER_REVIEW_BUNDLE.is_dir():
            manifest_path = LAUNCH_STUDIO_CUSTOMER_REVIEW_BUNDLE / 'BUNDLE_MANIFEST.json'
            bundle = read_json(manifest_path)
            archive_path = LAUNCH_STUDIO_CUSTOMER_REVIEW_BUNDLE.with_suffix('.zip')
            if (bundle.get('schema') != 'dio.launch_studio.customer_review_bundle.v1'
                    or bundle.get('asset_count') != 9
                    or bundle.get('source_bound_asset_count') != 9
                    or bundle.get('visual_passed_count') != 9
                    or bundle.get('baseline_and_messy_adversarial_media_identical') is not True
                    or bundle.get('adversarial_claim_hold_verified') is not True
                    or bundle.get('adversarial_held_claim_count') != 1
                    or bundle.get('adversarial_claim_text_sha256') != hashlib.sha256(b'Guaranteed employment for every participant.').hexdigest()
                    or 'not supported by an exact source quotation' not in str(bundle.get('adversarial_claim_hold_reason') or '')
                    or bundle.get('source_schedule_is_past_draft') is not True
                    or bundle.get('publication_authorized') is not False
                    or bundle.get('automatic_posting') is not False
                    or bundle.get('synthetic_fixture') is not True
                    or not (LAUNCH_STUDIO_CUSTOMER_REVIEW_BUNDLE / 'index.html').is_file()
                    or not archive_path.is_file()):
                raise ValueError('Launch Studio customer review package failed accuracy, evidence, or release-boundary checks')
            for item in bundle.get('files', []):
                path = LAUNCH_STUDIO_CUSTOMER_REVIEW_BUNDLE / item['path']
                if (not path.is_file() or path.stat().st_size != item.get('bytes')
                        or digest_file(path) != item.get('sha256')):
                    raise ValueError(f'Launch Studio review bundle hash/size mismatch: {item.get("path")}')
            with zipfile.ZipFile(archive_path) as archive:
                members = set(archive.namelist())
                expected = {path.relative_to(LAUNCH_STUDIO_CUSTOMER_REVIEW_BUNDLE).as_posix()
                            for path in LAUNCH_STUDIO_CUSTOMER_REVIEW_BUNDLE.rglob('*') if path.is_file()}
                if members != expected:
                    raise ValueError('Launch Studio ZIP member set differs from the reviewed bundle')
                for item in bundle.get('files', []):
                    if hashlib.sha256(archive.read(item['path'])).hexdigest() != item['sha256']:
                        raise ValueError(f'Launch Studio ZIP hash mismatch: {item["path"]}')
            product_specific_refs.extend([register(manifest_path), register(archive_path, digest_file(archive_path)),
                                          register(ROOT / 'scripts/build_launch_studio_customer_review_bundle.py')])
            for item in bundle.get('files', []):
                product_specific_refs.append(register(LAUNCH_STUDIO_CUSTOMER_REVIEW_BUNDLE / item['path'], item['sha256']))
            changes.append('The offline Launch Studio package now shows the adversarial “guaranteed employment” claim, its exact-source failure, and the held-out-of-marketing result. It explains that baseline/adversarial image hashes match because the claim was screened before rendering; the fixture tests claim governance, not visual variation. The package also retains nine reviewed creatives, source receipts, the past draft date, and the unpublished/unscheduled boundary.')
            limits.append('The curated package organizes nine synthetic fixtures and their existing review evidence. It does not validate brand or image rights, claim truth, platform rules, customer acceptance, future scheduling, or campaign results; the copied source schedule still requires owner replacement.')
        if seraph_ai_batch and name in {'AI IncidentRoom', 'AssuranceRoom', 'CriticalAI Assurance', 'CyberAssurance',
                                        'ControlDrift', 'DORA Vendor Assurance', 'ModelProof', 'ReleaseProof', 'DIO AI Assurance'}:
            product_specific_refs.append(register(SERAPH_TELEMETRY_AI_PROFILE_BATCH / 'BATCH_RECEIPT.json'))
            result = next(row for row in seraph_ai_batch['results'] if row.get('product_name') == name)
            case_dir = SERAPH_TELEMETRY_AI_PROFILE_BATCH / str(result['case_output_dir'])
            for file_row in result.get('files') or []:
                product_specific_refs.append(register(case_dir / file_row['path'], file_row.get('sha256')))
            if result.get('telemetry_requested'):
                changes.append('The customer route can bind opt-in Seraph telemetry to the case and include a separate hash-chain assessment in the held review pack and receipt. This synthetic case preserves signature, identity, and scope challenges; no telemetry claim grants approval or execution authority.')
                limits.append('Telemetry acceptance was exercised with synthetic data only. Hash-chain consistency does not establish trusted signer identity, source truth, completeness, persistence, live system state, or product qualification.')
            else:
                changes.append('The shared customer route leaves Seraph telemetry unrequested unless the case supplies it; the no-telemetry route did not invent a telemetry assessment.')
        if name == 'HOMS Exam':
            product_specific_refs.append(register(HOMS_GRADE_EXAM_AUDIT))
            exam_audit = read_json(HOMS_GRADE_EXAM_AUDIT)
            print_pdfs = exam_audit['print_ready_pdfs']
            product_specific_refs.append(register(HOMS_GRADE_EXAM_PDF_MANIFEST, print_pdfs['manifest_sha256']))
            product_specific_refs.append(register(ROOT / print_pdfs['bundle'], print_pdfs['bundle_sha256']))
            if HOMS_QUESTION_CAPS_ALIGNMENT.is_file():
                product_specific_refs.append(register(HOMS_QUESTION_CAPS_ALIGNMENT))
            if HOMS_GRADE12_CAPS_MAPPING_EVIDENCE.is_file():
                mapping_evidence = read_json(HOMS_GRADE12_CAPS_MAPPING_EVIDENCE)
                alignment = read_json(HOMS_QUESTION_CAPS_ALIGNMENT)
                grade12 = next(row for row in alignment.get('grades') or [] if row.get('grade') == 12)
                accuracy_review = read_json(HOMS_GRADE12_ACCURACY_REVISION) if HOMS_GRADE12_ACCURACY_REVISION.is_file() else {}
                grade12_dir = ROOT / 'deliverables/homs_random_grade_exam_set_20261101/grades/grade-12-business_studies'
                if (mapping_evidence.get('schema') != 'dio.homs.grade12_business_studies_caps_mapping_correction.v1'
                        or mapping_evidence.get('source_pdf_sha256') != grade12.get('caps_source_sha256')
                        or mapping_evidence.get('question_prompts_and_memo_marks_changed') is not False
                        or mapping_evidence.get('classroom_release_authorized') is not False
                        or len(mapping_evidence.get('new_question_mappings') or []) != 5
                        or len(grade12.get('question_mappings') or []) != 5
                        or accuracy_review.get('schema') != 'dio.homs.grade12_business_studies_accuracy_revision.v1'
                        or accuracy_review.get('current_assessment_sha256') != digest_file(grade12_dir / 'HOMS_GRADE_ASSESSMENT.json')
                        or accuracy_review.get('current_exam_docx_sha256') != digest_file(grade12_dir / 'GRADE_EXAM.docx')
                        or accuracy_review.get('current_memo_docx_sha256') != digest_file(grade12_dir / 'GRADE_MEMO.docx')
                        or accuracy_review.get('classroom_release_authorized') is not False
                        or accuracy_review.get('independent_moderation_decision') != 'NOT_ISSUED'):
                    raise ValueError('Grade 12 Business Studies CAPS topic correction is incomplete or crossed its review boundary')
                source_pdf = ROOT / mapping_evidence['source_pdf']
                if digest_file(source_pdf) != mapping_evidence['source_pdf_sha256']:
                    raise ValueError('Grade 12 Business Studies CAPS source PDF hash changed')
                for mapping in grade12['question_mappings']:
                    evidence_mapping = next((row for row in mapping_evidence['new_question_mappings']
                                             if row.get('question_id') == mapping.get('question_id')), None)
                    if mapping.get('question_id') == '1.1':
                        if (mapping.get('caps_topic') != 'Grade 12 Term 1: Macro environment — impact of recent legislation on business; Consumer Protection Act'
                                or [page.get('physical_pdf_page') for page in mapping.get('caps_pages') or []] != [38]
                                or mapping.get('prompt') != '1.1 The Consumer Protection Act is part of the Grade 12 CAPS topic on the impact of recent legislation. Using the ingredient information in the case, explain how this law could affect Koru\'s label decisions, state one check the owners should make before printing, and explain one possible effect of a misleading description. [8]'):
                            raise ValueError('Grade 12 question 1.1 does not match the reviewed grade-specific legislation map')
                    elif not evidence_mapping or evidence_mapping.get('caps_pages') != mapping.get('caps_pages'):
                        raise ValueError('Grade 12 CAPS question map differs from its correction evidence')
                    for citation in mapping.get('caps_pages') or []:
                        import subprocess
                        page_result = subprocess.run(
                            ['pdftotext', '-layout', '-f', str(citation['physical_pdf_page']), '-l', str(citation['physical_pdf_page']), str(source_pdf), '-'],
                            check=True, capture_output=True, text=True)
                        page_text = page_result.stdout.strip()
                        if hashlib.sha256(page_text.encode('utf-8')).hexdigest() != citation.get('page_text_sha256'):
                            raise ValueError('Grade 12 CAPS page text hash does not match the cited physical PDF page')
                product_specific_refs.extend([register(HOMS_GRADE12_CAPS_MAPPING_EVIDENCE), register(HOMS_GRADE12_ACCURACY_REVISION)])
                changes.append('A source audit found the original Grade 12 Business Studies Q1.1 mapped prior-year environmental categories. It now applies the Grade 12 macro-environment legislation topic to the Consumer Protection Act and Koru’s label, with the current official CAPS page 38 hash-bound. The 50-mark paper is explicitly a focused assessment rather than a full Grade 12 examination; its memo was revised to use positive, observable marking points. The subject educator must still review the draft.')
                limits.append('This corrects topic-level source traceability only. Full CAPS coverage, term fit, item validity and educator approval remain open.')
            if HOMS_GRADE_EXAM_INDEX.is_file():
                product_specific_refs.append(register(HOMS_GRADE_EXAM_INDEX))
            grade2_correction = ROOT / 'deliverables/homs_random_grade_exam_set_20261101/GRADE02_CONTENT_CORRECTION_20261102.json'
            grade5_correction = ROOT / 'deliverables/homs_random_grade_exam_set_20261101/GRADE05_CONTENT_CORRECTION_20261102.json'
            if grade5_correction.is_file():
                product_specific_refs.append(register(grade5_correction))
            if grade2_correction.is_file():
                correction = read_json(grade2_correction)
                if (correction.get('schema') != 'dio.homs.grade_exam_content_correction.v1'
                        or correction.get('grade') != 2
                        or correction.get('question_id') != '1.4'
                        or correction.get('question_mark_total') != correction.get('memo_mark_total')
                        or correction.get('classroom_release_authorized') is not False):
                    raise ValueError('Grade 2 English item correction is stale or crossed the educator-release boundary')
                product_specific_refs.append(register(grade2_correction))
            for grade, question_id in ((3, '1.2'), (4, '1.4'), (10, '1.4')):
                correction_path = ROOT / f'deliverables/homs_random_grade_exam_set_20261101/GRADE{grade:02d}_CONTENT_CORRECTION_20261102.json'
                if correction_path.is_file():
                    correction = read_json(correction_path)
                    if (correction.get('schema') != 'dio.homs.grade_exam_content_correction.v1'
                            or correction.get('grade') != grade
                            or correction.get('question_id') != question_id
                            or correction.get('question_mark_total') != correction.get('memo_mark_total')
                            or correction.get('classroom_release_authorized') is not False):
                            raise ValueError(f'Grade {grade} item correction is stale or crossed the educator-release boundary')
                    product_specific_refs.append(register(correction_path))
            grade10_reasoning_correction = ROOT / 'deliverables/homs_random_grade_exam_set_20261101/GRADE10_DISTANCE_SPEED_REASONING_CORRECTION_20261102.json'
            if grade10_reasoning_correction.is_file():
                reasoning_correction = read_json(grade10_reasoning_correction)
                if (reasoning_correction.get('schema') != 'dio.homs.grade10_distance_speed_reasoning_correction.v1'
                        or reasoning_correction.get('question_ids') != ['1.1', '1.2']
                        or reasoning_correction.get('mechanical_moderation_state') != 'PASS'
                        or reasoning_correction.get('classroom_release_authorized') is not False):
                    raise ValueError('Grade 10 distance/speed reasoning correction is stale or crossed the educator-release boundary')
                product_specific_refs.append(register(grade10_reasoning_correction))
                changes.append('Grade 10 Physical Sciences now uses a specified reversal to distinguish path length from displacement and compares average speed with average velocity for the same interval. The revised assessment and memo are regenerated and mechanically checked; educator review remains pending.')
            changes.append('A randomized subject assignment across grades 1–12 has current source-hash, prompt/memo content, mark-reconciliation and mechanical moderation evidence. All 60 questions link to a CAPS topic, physical PDF page and page-text hash. Twenty-four printable exam/memo PDFs are hash-bound to their editable DOCX sources, and the index exposes both formats. Subject educators must confirm content and term fit before classroom use.')
            if HOMS_EXAM_CUSTOMER_DEMO.is_dir():
                exam_package = HOMS_EXAM_CUSTOMER_DEMO / 'CUSTOMER_PACKAGE_RECEIPT.json'
                if exam_package.is_file():
                    packet_receipt = read_json(exam_package)
                    for output in packet_receipt.get('outputs', []):
                        path = HOMS_EXAM_CUSTOMER_DEMO / output['path']
                        if path.is_file():
                            register(path, output.get('sha256'))
                    product_specific_refs.append(register(exam_package))
                execution = HOMS_EXAM_CUSTOMER_DEMO / 'CUSTOMER_EXECUTION_RECEIPT.json'
                if execution.is_file(): product_specific_refs.append(register(execution))
                preview = HOMS_EXAM_CUSTOMER_DEMO / 'CUSTOMER_EXAM_PACKAGE.html'
                if preview.is_file(): product_specific_refs.append(register(preview))
                disposition = 'CURRENT_HELD_EXECUTION_VERIFIED'
                changes.append('The customer entry point now selects a grade and delivers its exact randomized exam/memo with matching CAPS topic/page references; the Grade 3 Mathematics route was executed and hash-bound.')
        if name == 'HOMS Exam' and HOMS_EXAM_CUSTOMER_GRADE_BATCH.is_dir():
            batch_receipt_path = HOMS_EXAM_CUSTOMER_GRADE_BATCH / 'HOMS_EXAM_CUSTOMER_GRADE_BATCH_RECEIPT.json'
            batch = read_json(batch_receipt_path)
            grades = batch.get('results') or []
            if len(grades) != 12 or {int(row.get('grade') or 0) for row in grades} != set(range(1, 13)):
                raise ValueError('HOMS Exam customer grade batch must include all Grades 1–12 exactly once')
            if batch.get('classroom_release_authorized') is not False or batch.get('educator_review_required') is not True:
                raise ValueError('HOMS Exam customer grade batch crossed its educator/release boundary')
            for row in grades:
                package_path = HOMS_EXAM_CUSTOMER_GRADE_BATCH / row['package_receipt']
                package_doc = read_json(package_path)
                if (package_doc.get('caps_source_page_excerpt_hashes_match_alignment') is not True
                        or package_doc.get('caps_source_page_excerpt_count', 0) < row.get('question_count', 0)):
                    raise ValueError(f"HOMS Exam Grade {row.get('grade')} is missing hash-verified in-package CAPS excerpts")
                quality = row.get('educator_item_quality_review') or {}
                if (quality.get('question_row_count') != row.get('question_count')
                        or quality.get('blank_educator_decisions') is not True
                        or quality.get('automated_memo_mark_balance_all_pass') is not True
                        or sum((quality.get('draft_cognitive_level_counts') or {}).values()) != row.get('question_count')
                        or quality.get('unclassified_draft_cognitive_label_count', -1) < 0
                        or quality.get('independent_moderation_decision') != 'NOT_ISSUED'):
                    raise ValueError(f"HOMS Exam Grade {row.get('grade')} lacks its complete held educator item-quality review sheet")
            product_specific_refs.append(register(batch_receipt_path))
            product_specific_refs.append(register(ROOT / 'scripts/validate_homs_exam_item_quality_review.py'))
            for grade_row in grades:
                package_path = HOMS_EXAM_CUSTOMER_GRADE_BATCH / grade_row['package_receipt']
                execution_path = HOMS_EXAM_CUSTOMER_GRADE_BATCH / grade_row['execution_receipt']
                product_specific_refs.append(register(package_path, grade_row['package_receipt_sha256']))
                product_specific_refs.append(register(execution_path, grade_row['execution_receipt_sha256']))
                for relative, digest in (grade_row.get('output_hashes') or {}).items():
                    grade_dir = HOMS_EXAM_CUSTOMER_GRADE_BATCH / f"grade-{int(grade_row['grade']):02d}"
                    product_specific_refs.append(register(grade_dir / relative, digest))
            if HOMS_BEST_EXAM_CANDIDATE_SHORTLIST.is_file():
                shortlist = read_json(HOMS_BEST_EXAM_CANDIDATE_SHORTLIST)
                shortlist_rows = shortlist.get('items') or []
                if (shortlist.get('schema') != 'dio.homs.exam.candidate_shortlist.v2'
                        or len(shortlist_rows) != 12
                        or {int(row.get('grade') or 0) for row in shortlist_rows} != set(range(1, 13))
                        or shortlist.get('classroom_release_authorized') is not False
                        or shortlist.get('educator_review_required') is not True
                        or shortlist.get('independent_moderation_decision') != 'NOT_ISSUED'):
                    raise ValueError('HOMS best-exam shortlist is incomplete or crossed its educator/release boundary')
                for candidate in shortlist_rows:
                    grade = int(candidate['grade'])
                    source_batch = OUTPUT / candidate['selected_batch']
                    source_receipt_path = source_batch / 'HOMS_EXAM_CUSTOMER_GRADE_BATCH_RECEIPT.json'
                    source_receipt = read_json(source_receipt_path)
                    source_grade = next((row for row in source_receipt.get('results', []) if int(row.get('grade') or 0) == grade), None)
                    if source_grade is None:
                        raise ValueError(f'HOMS best-exam shortlist Grade {grade} has no receipt source row')
                    declared_receipt_hash = (shortlist.get('batch_receipt_sha256') or {}).get(source_batch.name)
                    if not declared_receipt_hash or hashlib.sha256(source_receipt_path.read_bytes()).hexdigest() != declared_receipt_hash:
                        raise ValueError(f'HOMS best-exam shortlist Grade {grade} source receipt hash is stale')
                    product_specific_refs.append(register(source_receipt_path, declared_receipt_hash))
                    for artifact_kind, receipt_field in (('exam_pdf', 'exam_pdf_sha256'), ('memo_pdf', 'memo_pdf_sha256')):
                        candidate_artifact = (candidate.get('artifacts') or {}).get(artifact_kind) or {}
                        artifact_path = ROOT / candidate_artifact.get('path', '')
                        expected_hash = source_grade.get(receipt_field)
                        if (not artifact_path.is_file()
                                or candidate_artifact.get('sha256') != expected_hash
                                or hashlib.sha256(artifact_path.read_bytes()).hexdigest() != expected_hash):
                            raise ValueError(f'HOMS best-exam shortlist Grade {grade} {artifact_kind} does not match its source receipt')
                        product_specific_refs.append(register(artifact_path, expected_hash))
                    grade_dir = source_batch / f'grade-{grade:02d}'
                    output_hashes = source_grade.get('output_hashes') or {}
                    for relative in (
                            f'documents/GRADE_{grade:02d}_DRAFT_EXAM.docx',
                            f'documents/GRADE_{grade:02d}_DRAFT_MARKING_MEMO.docx',
                            'EDUCATOR_ITEM_QUALITY_REVIEW.csv',
                            'EDUCATOR_ITEM_QUALITY_REVIEW_GUIDE.md',
                            'EDUCATOR_ITEM_QUALITY_REVIEW_VALIDATION.json'):
                        expected_hash = output_hashes.get(relative)
                        review_artifact = grade_dir / relative
                        if not expected_hash or not review_artifact.is_file():
                            raise ValueError(f'HOMS best-exam shortlist Grade {grade} is missing bound review artifact {relative}')
                        product_specific_refs.append(register(review_artifact, expected_hash))
                    review = candidate.get('educator_review') or {}
                    if review.get('educator_decisions_blank') is not True or review.get('mark_balance_verified') is not True:
                        raise ValueError(f'HOMS best-exam shortlist Grade {grade} has unverified review/mark state')
                product_specific_refs.append(register(HOMS_BEST_EXAM_CANDIDATE_SHORTLIST))
            if HOMS_CURATED_CANDIDATE_BUNDLE.is_dir():
                bundle_manifest_path = HOMS_CURATED_CANDIDATE_BUNDLE / 'CANDIDATE_BUNDLE_MANIFEST.json'
                bundle_manifest = read_json(bundle_manifest_path)
                bundle_grades = bundle_manifest.get('grades') or []
                bundle_zip = HOMS_CURATED_CANDIDATE_BUNDLE / 'HOMS_RANDOMIZED_EXAM_CANDIDATES_GRADES_01_12.zip'
                if (bundle_manifest.get('schema') != 'dio.homs.exam.curated_candidate_bundle.v1'
                        or len(bundle_grades) != 12
                        or {int(row.get('grade') or 0) for row in bundle_grades} != set(range(1, 13))
                        or bundle_manifest.get('classroom_release_authorized') is not False
                        or bundle_manifest.get('educator_review_required') is not True
                        or bundle_manifest.get('independent_moderation_decision') != 'NOT_ISSUED'
                        or not bundle_zip.is_file()):
                    raise ValueError('HOMS curated candidate bundle is incomplete or crossed its educator/release boundary')
                shortlist_by_grade = {int(row['grade']): row for row in shortlist_rows}
                for grade_row in bundle_grades:
                    grade = int(grade_row['grade'])
                    expected_candidate = shortlist_by_grade.get(grade)
                    if expected_candidate is None:
                        raise ValueError(f'HOMS curated bundle has unexpected Grade {grade}')
                    for kind, rel_key in (('exam_pdf', 'exam_pdf'), ('memo_pdf', 'memo_pdf')):
                        bundle_rel = grade_row.get(rel_key)
                        expected_sha = expected_candidate['artifacts'][kind]['sha256']
                        bundle_file = HOMS_CURATED_CANDIDATE_BUNDLE / bundle_rel
                        if (not bundle_file.is_file() or digest_file(bundle_file) != expected_sha
                                or not any(row.get('path') == bundle_rel and row.get('sha256') == expected_sha
                                           for row in grade_row.get('files', []))):
                            raise ValueError(f'HOMS curated bundle Grade {grade} {kind} differs from the selected receipt-bound candidate')
                for bundle_artifact in bundle_manifest.get('bundle_artifacts', []):
                    bundle_path = HOMS_CURATED_CANDIDATE_BUNDLE / bundle_artifact['path']
                    if not bundle_path.is_file() or digest_file(bundle_path) != bundle_artifact.get('sha256'):
                        raise ValueError(f'HOMS curated bundle artifact is missing or changed: {bundle_artifact.get("path")}')
                    product_specific_refs.append(register(bundle_path, bundle_artifact['sha256']))
                if bundle_manifest.get('selection_manifest_sha256') != digest_file(HOMS_BEST_EXAM_CANDIDATE_SHORTLIST):
                    raise ValueError('HOMS curated bundle is stale against the current candidate shortlist')
                product_specific_refs.append(register(bundle_manifest_path))
                product_specific_refs.append(register(bundle_zip))
            disposition = 'CURRENT_HELD_EXECUTION_VERIFIED'
            changes.append('The randomized customer delivery route has now been executed for every grade, 1–12. Each package includes hash-verified excerpts from every cited CAPS page, alongside editable and printable exam/memo files, source-bound CAPS mappings, and a question-level educator review matrix for reasoning demand, grade/term fit, CAPS alignment, memo coverage, marks and language. All question allocations reconcile to memo point marks across 12 grades; draft cognitive labels are normalized and non-taxonomy labels are explicitly flagged for educator classification.')
            changes.append('A content audit found Grade 1 Question 1.1 awarded two explanation marks that its prompt did not request. The canonical prompt now explicitly asks for one reason per healthy action; the assessment JSON, source receipt, CAPS mapping, exam/memo DOCX and print PDF manifest were refreshed, then all 12 grade packages were regenerated against the current hashes.')
            changes.append('An item-level review found duplicated or unsolicited Grade 2 English marks in Questions 1.1 and 1.2. The revised four-mark rubrics now award one mark for each distinct printed-stimulus detail; CAPS question mappings, DOCX/PDF files and the customer grade batch were refreshed while preserving random seed 20261101.')
            changes.append('Grade 2 English Question 1.4 now asks learners to rewrite a complete sentence in the singular, with four memo points for quantity, noun number, adjective retention and sentence punctuation. The randomized grade pack, print files, CAPS question mapping, customer delivery batch and 12-grade moderation route were refreshed and hash-checked; educator approval remains pending.')
            changes.append('Grade 5 Natural Sciences and Technology was corrected after a full item-to-source review found unrelated mixtures/ice questions mapped to metals and flour-paste CAPS pages. The five items now assess the Grade 5 concrete-processing example, before/after material properties, fair testing and result recording, mapped to relevant official CAPS pages. Grade 3 Mathematics Question 1.2 now asks learners to show equal grouping and report any remainder, with follow-through credit from Question 1.1. Grade 4 Mathematics Question 1.4 now asks for column subtraction, visible regrouping and an addition check so the seven-mark memo matches the requested work. Current exam/memo hashes, CAPS mappings, print files, customer routes, moderation and Learning Studio source bindings were rebuilt across all 12 grades.')
            changes.append('Grade 10 Physical Sciences Question 1.4 now assesses both final velocity and signed displacement from the velocity-time graph area, matching its 11-mark allocation. The mapping cites the official constant-acceleration content and graph displacement outcome; refreshed source excerpts and all dependent grade routes remain held for educator review.')
            limits = ['These are randomized CAPS-source-mapped drafts, not a claim of full curriculum coverage or educator approval. Draft cognitive-demand labels and balanced mark allocations do not establish question quality. Subject educators must classify or confirm every item, complete the review matrix, confirm grade/term fit, reasoning demand, memo correctness and classroom suitability; independent moderation remains NOT ISSUED.']
        if name == 'HOMS Exam' and (HOMS_CAPS_SOURCE_EXCERPT_REVIEW / 'CAPS_SOURCE_EXCERPT_REVIEW_MANIFEST.json').is_file():
            excerpt_manifest_path = HOMS_CAPS_SOURCE_EXCERPT_REVIEW / 'CAPS_SOURCE_EXCERPT_REVIEW_MANIFEST.json'
            excerpt_manifest = read_json(excerpt_manifest_path)
            alignment_hash = hashlib.sha256(HOMS_QUESTION_CAPS_ALIGNMENT.read_bytes()).hexdigest()
            if (excerpt_manifest.get('schema') != 'dio.homs.caps_question_source_excerpt_review.v1'
                    or excerpt_manifest.get('grade_count') != 12
                    or excerpt_manifest.get('question_count') != 60
                    or excerpt_manifest.get('question_page_excerpt_count') != sum(len(mapping.get('caps_pages') or []) for grade in read_json(HOMS_QUESTION_CAPS_ALIGNMENT).get('grades', []) for mapping in grade.get('question_mappings', []))
                    or excerpt_manifest.get('source_alignment_sha256') != alignment_hash
                    or excerpt_manifest.get('page_text_hash_validation') != 'PASS_ALL_CITATIONS_MATCH_BYTE_VERIFIED_SOURCE_PDF_EXTRACTION'
                    or excerpt_manifest.get('classroom_release_authorized') is not False
                    or excerpt_manifest.get('independent_educator_review') != 'PENDING'):
                raise ValueError('HOMS CAPS source excerpt pack is incomplete, stale against the alignment, has an unverified page-text hash, or crossed its educator-release boundary')
            product_specific_refs.extend([register(excerpt_manifest_path), register(HOMS_CAPS_SOURCE_EXCERPT_REVIEW / 'index.html')])
            for grade_excerpt in excerpt_manifest.get('grades') or []:
                if grade_excerpt.get('question_count') != 5 or grade_excerpt.get('educator_review_state') != 'PENDING_EDUCATOR_CONFIRMATION':
                    raise ValueError(f"HOMS CAPS source excerpt review is incomplete for Grade {grade_excerpt.get('grade')}")
                product_specific_refs.extend([
                    register(HOMS_CAPS_SOURCE_EXCERPT_REVIEW / grade_excerpt['html'], grade_excerpt.get('html_sha256')),
                    register(HOMS_CAPS_SOURCE_EXCERPT_REVIEW / grade_excerpt['csv'], grade_excerpt.get('csv_sha256')),
                ])
            changes.append('A 12-grade educator aid places all 60 exam prompts beside the complete current set of mapped official CAPS pages. The qualification build verifies every extracted-page SHA-256 against the current alignment map, checks the alignment-file hash binding, and confirms the source PDFs were byte-verified. It is explicitly a review aid; educator confirmation remains pending.')
            limits.append('Source excerpts reduce lookup effort and bind to verified official PDF bytes; they do not prove complete CAPS coverage, semantic item validity, term fit or educator approval.')
            exam_pack = ROOT / 'deliverables/homs_random_grade_exam_set_20261101'
            for path in (HOMS_GRADE_EXAM_AUDIT,
                         OUTPUT / 'HOMS_RANDOM_GRADE_EXAM_VISUAL_RENDER_AUDIT_20261104_V14.json',
                         exam_pack / 'index.html',
                         exam_pack / 'GRADE07_SOURCE_TITLE_CORRECTION_20261102.json',
                         exam_pack / 'GRADE07_CONTENT_CORRECTION_20261102.json',
                         exam_pack / 'GRADE04_FRACTION_MEMO_CORRECTION_20261102.json',
                         exam_pack / 'HOMS_RANDOM_GRADE_EXAMS_AND_MEMOS_20261101.zip',
                         exam_pack / 'HOMS_RANDOM_GRADE_EXAMS_AND_MEMOS_PRINT_READY_20261101.zip'):
                if path.is_file():
                    product_specific_refs.append(register(path))
        if name == 'HOMS Exam' and HOMS_SUBJECT_REPRODUCIBILITY_AUDIT.is_file():
            assignment_audit = read_json(HOMS_SUBJECT_REPRODUCIBILITY_AUDIT)
            if (assignment_audit.get('result') != 'PASS'
                    or assignment_audit.get('assignment_draw_reconstructed') is not True
                    or assignment_audit.get('caps_identity_rows_match_assignments') is not True
                    or len(assignment_audit.get('phase_results') or []) != 4
                    or any(not row.get('no_replacement_satisfied') or not row.get('all_assignments_in_pool')
                           or not row.get('reconstructed_rows_match') for row in assignment_audit.get('phase_results') or [])
                    or assignment_audit.get('classroom_release_authorized') is not False):
                raise ValueError('HOMS randomized subject draw could not be independently reconstructed from its seed and pools')
            product_specific_refs.append(register(HOMS_SUBJECT_REPRODUCIBILITY_AUDIT))
            product_specific_refs.append(register(ROOT / 'scripts/audit_homs_random_subject_reproducibility.py'))
            changes.append('A separate reproducibility audit reconstructs the Grade 1–12 subject draw from the recorded seed, records the approved pool and assignments for each CAPS phase, checks no replacement, and matches each grade to its verified CAPS document identity. The original assignment manifest stays unchanged so downstream package hashes remain valid.')
        if name == 'HOMS Moderate' and HOMS_QUESTION_CAPS_ALIGNMENT.is_file():
            product_specific_refs.append(register(HOMS_QUESTION_CAPS_ALIGNMENT))
        if name == 'HOMS Moderate':
            product_specific_refs.append(register(HOMS_MODERATION_BATCH))
            changes.append('Current mechanical pre-moderation passed all twelve randomized grade exam packs; the independent moderation decision remains unissued.')
            if HOMS_MODERATE_COHORT_DEMO.is_dir():
                cohort_execution = read_json(HOMS_MODERATE_COHORT_DEMO / 'CUSTOMER_EXECUTION_RECEIPT.json')
                cohort_package = cohort_execution.get('receipt') or {}
                cohort_report = HOMS_MODERATE_COHORT_DEMO / 'HOMS_COHORT_ANALYSIS.json'
                for path in (HOMS_MODERATE_COHORT_DEMO / 'CUSTOMER_EXECUTION_RECEIPT.json',
                             HOMS_MODERATE_COHORT_DEMO / 'CUSTOMER_PACKAGE_RECEIPT.json',
                             cohort_report):
                    product_specific_refs.append(register(path))
                for output in cohort_package.get('outputs', []):
                    if isinstance(output, dict) and output.get('path', '').endswith(('.docx', '.html')):
                        product_specific_refs.append(register(HOMS_MODERATE_COHORT_DEMO / output['path'], output.get('sha256')))
                changes.append('The Moderate route now computes aggregate score distribution, item facility and item-to-rest correlation from a source-hashed pseudonymous cohort score matrix; synthetic Grade 10 execution is held for educator review.')
                limits = ['Cohort analysis is descriptive only and has been exercised with synthetic records. It does not apply grading thresholds, rank learners, decide assessment quality, or issue moderation approval; real score records and educator interpretation remain required.']
                disposition = 'CURRENT_HELD_EXECUTION_VERIFIED'
            if HOMS_MODERATE_CUSTOMER_DEMO.is_dir():
                package_path = HOMS_MODERATE_CUSTOMER_DEMO / 'CUSTOMER_PACKAGE_RECEIPT.json'
                if package_path.is_file():
                    package_receipt = read_json(package_path)
                    for output in package_receipt.get('outputs', []):
                        path = HOMS_MODERATE_CUSTOMER_DEMO / output['path']
                        if path.is_file():
                            register(path, output.get('sha256'))
                    product_specific_refs.append(register(package_path))
                for path in (HOMS_MODERATE_CUSTOMER_DEMO / 'CUSTOMER_EXECUTION_RECEIPT.json',
                             HOMS_MODERATE_CUSTOMER_DEMO / 'CUSTOMER_MODERATION_REVIEW.html'):
                    if path.is_file(): product_specific_refs.append(register(path))
                changes.append('A customer route selects a randomized grade and runs the existing seven structural pre-moderation checks against the exact source DOCX paper/memo. Grade 3 Mathematics passed 7/7; no independent moderation decision is issued.')
                disposition = 'CURRENT_HELD_EXECUTION_VERIFIED'
            if HOMS_MODERATE_CUSTOMER_GRADE_BATCH.is_dir():
                batch_path = HOMS_MODERATE_CUSTOMER_GRADE_BATCH / 'HOMS_MODERATE_CUSTOMER_GRADE_BATCH_RECEIPT.json'
                batch = read_json(batch_path)
                grade_rows = batch.get('results') or []
                if (len(grade_rows) != 12
                        or {int(row.get('grade') or 0) for row in grade_rows} != set(range(1, 13))
                        or batch.get('mechanical_pass_count') != 12
                        or batch.get('independent_moderation_decision') != 'NOT_ISSUED'
                        or batch.get('classroom_release_authorized') is not False):
                    raise ValueError('HOMS Moderate customer batch is not twelve held, eight-check grade executions')
                product_specific_refs.append(register(batch_path))
                for grade_row in grade_rows:
                    product_specific_refs.append(register(
                        HOMS_MODERATE_CUSTOMER_GRADE_BATCH / grade_row['package_receipt'],
                        grade_row['package_receipt_sha256'],
                    ))
                    product_specific_refs.append(register(
                        HOMS_MODERATE_CUSTOMER_GRADE_BATCH / grade_row['execution_receipt'],
                        grade_row['execution_receipt_sha256'],
                    ))
                    grade_dir = HOMS_MODERATE_CUSTOMER_GRADE_BATCH / f"grade-{int(grade_row['grade']):02d}"
                    package = read_json(grade_dir / 'CUSTOMER_PACKAGE_RECEIPT.json')
                    report_path = grade_dir / 'HOMS_MECHANICAL_PREMODERATION_REPORT.json'
                    moderation_report = read_json(report_path)
                    alignment_check = next((row for row in moderation_report.get('checks', [])
                                            if row.get('check') == 'caps_question_alignment_binding'), {})
                    if (package.get('check_count') != 8 or package.get('passed_checks') != 8
                            or package.get('source_caps_alignment_sha256') != grade_row.get('source_caps_alignment_sha256')
                            or alignment_check.get('state') != 'PASS'
                            or moderation_report.get('release_authorized') is not False):
                        raise ValueError(f"HOMS Moderate Grade {grade_row['grade']} lacks a passing exact question-to-CAPS binding")
                    for output in grade_row.get('outputs') or []:
                        product_specific_refs.append(register(grade_dir / output['path'], output.get('sha256')))
                changes.append('HOMS Moderate now checks exact question IDs and prompts against the selected randomized grade CAPS map, validates cited page/text hashes and confirms the local official CAPS PDF bytes. All 12 grades pass the new eighth source-binding check alongside the seven prior structural checks.')
                if HOMS_MODERATE_MASTER_INDEX.is_file() and HOMS_MODERATE_MASTER_INDEX_MANIFEST.is_file():
                    master_manifest = read_json(HOMS_MODERATE_MASTER_INDEX_MANIFEST)
                    if (master_manifest.get('schema') != 'dio.homs.moderate.master_index.v1'
                            or master_manifest.get('grade_count') != 12
                            or master_manifest.get('independent_moderation_decision') != 'NOT_ISSUED'
                            or master_manifest.get('classroom_release_authorized') is not False
                            or master_manifest.get('batch_receipt_sha256') != hashlib.sha256(batch_path.read_bytes()).hexdigest()
                            or master_manifest.get('assignment_manifest_sha256') != hashlib.sha256((ROOT / 'deliverables/homs_random_grade_exam_set_20261101/RANDOM_SUBJECT_ASSIGNMENTS.json').read_bytes()).hexdigest()
                            or master_manifest.get('index_sha256') != hashlib.sha256(HOMS_MODERATE_MASTER_INDEX.read_bytes()).hexdigest()
                            or len(master_manifest.get('grades') or []) != 12):
                        raise ValueError('HOMS Moderate master index failed batch, assignment, release-state, or artifact hash checks')
                    product_specific_refs.extend([register(HOMS_MODERATE_MASTER_INDEX), register(HOMS_MODERATE_MASTER_INDEX_MANIFEST),
                                                  register(ROOT / 'scripts/build_homs_moderate_master_index.py')])
                    changes.append('The latest HOMS Moderate customer index links the Grade 1–12 randomized exam and memo PDFs, individual educator review pages and source-bound eight-check reports; the index validates every linked batch output hash and remains held for independent subject moderation.')
                changes.append('The refreshed Grade 2 route used the corrected question/memo set and matched the updated assessment, CAPS alignment and print hashes; the grade remains a draft pending educator moderation.')
                limits = ['All 12 route runs are controlled synthetic drafts. Structural checks do not establish subject accuracy, CAPS coverage or moderation approval; educator review is required, independent moderation remains NOT ISSUED, and classroom release is unauthorized.']
                disposition = 'CURRENT_HELD_EXECUTION_VERIFIED'
        if name == 'HOMS Curriculum':
            if HOMS_QUESTION_CAPS_ALIGNMENT.is_file():
                product_specific_refs.append(register(HOMS_QUESTION_CAPS_ALIGNMENT))
            for path in (HOMS_CURRICULUM_CAPS_EVIDENCE, HOMS_CURRICULUM_TRACEABILITY_EVIDENCE):
                if path.is_file():
                    product_specific_refs.append(register(path))
            if HOMS_CURRICULUM_CUSTOMER_EXECUTION.is_dir():
                curriculum_receipt = HOMS_CURRICULUM_CUSTOMER_EXECUTION / 'CUSTOMER_PACKAGE_RECEIPT.json'
                curriculum_binding = HOMS_CURRICULUM_CUSTOMER_EXECUTION / 'CURRICULUM_SOURCE_BINDING.json'
                for path in (curriculum_receipt, curriculum_binding,
                             HOMS_CURRICULUM_CUSTOMER_EXECUTION / 'CURRICULUM_ALIGNMENT_MATRIX.csv',
                             HOMS_CURRICULUM_CUSTOMER_EXECUTION / 'CURRICULUM_REVIEW.md'):
                    if path.is_file():
                        product_specific_refs.append(register(path))
                if curriculum_receipt.is_file():
                    for output_row in (read_json(curriculum_receipt).get('outputs') or []):
                        product_specific_refs.append(register(HOMS_CURRICULUM_CUSTOMER_EXECUTION / output_row['path'], output_row.get('sha256')))
                changes.append('A customer-packet route maps supplied Grade 8 Social Sciences plan rows to hash-checked official CAPS pages and now includes a structured CSV input template plus a blank source-row-bound curriculum-owner review sheet for term fit, scope, sequence and allocation. The controlled sample yielded only unresolved/review states; omissions are not inferred and human curriculum-owner review remains required.')
                limits = ['Automated customer mapping currently covers Grade 8 Social Sciences only. The controlled sample plan is not a complete-plan attestation; no omissions, adequacy, school compliance, or approval are established.']
                disposition = 'CURRENT_HELD_EXECUTION_VERIFIED'
            if HOMS_CURRICULUM_RANDOMIZED_SPINE_BATCH.is_dir():
                batch_receipt_path = HOMS_CURRICULUM_RANDOMIZED_SPINE_BATCH / 'HOMS_CURRICULUM_RANDOMIZED_SPINE_GRADE_BATCH_RECEIPT.json'
                batch_execution_path = HOMS_CURRICULUM_RANDOMIZED_SPINE_BATCH / 'CUSTOMER_EXECUTION_RECEIPT.json'
                batch_receipt = read_json(batch_receipt_path)
                batch_execution = read_json(batch_execution_path)
                batch_rows = batch_receipt.get('grades') or []
                if (batch_receipt.get('schema') != 'dio.homs.curriculum.randomized_exam_spine_grade_batch.v1'
                        or batch_receipt.get('grade_count') != 12 or len(batch_rows) != 12
                        or {row.get('grade') for row in batch_rows} != set(range(1, 13))
                        or batch_receipt.get('randomized_seed') != 20261101
                        or batch_receipt.get('synthetic_fixture') is not True
                        or batch_receipt.get('term_fit_inferred') is not False
                        or batch_receipt.get('candidate_omissions_computed') is not False
                        or batch_receipt.get('professional_conclusion') is not False
                        or batch_receipt.get('source_alignment_path') != HOMS_QUESTION_CAPS_ALIGNMENT.relative_to(ROOT).as_posix()
                        or batch_receipt.get('source_alignment_sha256') != digest_file(HOMS_QUESTION_CAPS_ALIGNMENT)
                        or batch_receipt.get('release_authorized') is not False
                        or batch_execution.get('batch_receipt_sha256') != digest_file(batch_receipt_path)
                        or batch_execution.get('release_authorized') is not False):
                    raise ValueError('HOMS Curriculum randomized grade spine batch exceeded its held source-mapping boundary')
                product_specific_refs.extend([register(batch_receipt_path), register(batch_execution_path), register(HOMS_QUESTION_CAPS_ALIGNMENT)])
                batch_input_dir = HOMS_CURRICULUM_RANDOMIZED_SPINE_INPUT_BATCH
                for grade_row in batch_rows:
                    grade_number = int(grade_row['grade'])
                    grade_dir = HOMS_CURRICULUM_RANDOMIZED_SPINE_BATCH / f'grade-{grade_number:02d}'
                    package_path = grade_dir / 'CUSTOMER_PACKAGE_RECEIPT.json'
                    execution_path = grade_dir / 'CUSTOMER_EXECUTION_RECEIPT.json'
                    package = read_json(package_path)
                    execution = read_json(execution_path)
                    if (package.get('grade') != grade_number
                            or package.get('subject') != grade_row.get('subject')
                            or package.get('randomization_seed') != 20261101
                            or package.get('mapped_candidate_count') != 5
                            or package.get('review_required_count') != 1
                            or package.get('term_fit_inferred') is not False
                            or package.get('candidate_omissions_computed') is not False
                            or package.get('professional_conclusion') is not False
                            or package.get('external_release_authorized') is not False
                            or execution.get('release_authorized') is not False
                            or execution.get('external_effects') is not False):
                        raise ValueError(f'HOMS Curriculum grade {grade_number} did not preserve candidate/review states')
                    template_path = grade_dir / 'CURRICULUM_PLAN_ENTRY_TEMPLATE.csv'
                    with template_path.open(encoding='utf-8-sig', newline='') as template_handle:
                        template_rows = list(csv.DictReader(template_handle))
                    expected_question_ids = [f'1.{number}' for number in range(1, 6)]
                    if (len(template_rows) != 5
                            or [row.get('question_id') for row in template_rows] != expected_question_ids
                            or any(row.get('grade') != str(grade_number)
                                   or row.get('subject') != grade_row.get('subject')
                                   or row.get('term') or row.get('topic')
                                   for row in template_rows)):
                        raise ValueError(f'HOMS Curriculum grade {grade_number} plan-entry template is not a blank, exact question set')
                    grade_input_dir = batch_input_dir / f'grade-{grade_number:02d}'
                    product_specific_refs.append(register(grade_input_dir / 'CUSTOMER_PACKET.json', grade_row['input_packet_sha256']))
                    product_specific_refs.append(register(grade_input_dir / 'synthetic_customer_plan.csv', grade_row['source_plan_sha256']))
                    product_specific_refs.append(register(execution_path, grade_row['execution_receipt_sha256']))
                    for output in grade_row.get('outputs') or []:
                        product_specific_refs.append(register(ROOT / output['path'], output.get('sha256')))
                if not HOMS_CURRICULUM_MASTER_INDEX.is_file() or not HOMS_CURRICULUM_MASTER_INDEX_MANIFEST.is_file():
                    raise ValueError('HOMS Curriculum master grade picker or manifest is missing')
                curriculum_index = read_json(HOMS_CURRICULUM_MASTER_INDEX_MANIFEST)
                curriculum_html = HOMS_CURRICULUM_MASTER_INDEX.read_text(encoding='utf-8')
                linked = curriculum_index.get('linked_review_artifacts') or []
                linked_match = all(
                    (HOMS_CURRICULUM_RANDOMIZED_SPINE_BATCH / item['path']).is_file()
                    and digest_file(HOMS_CURRICULUM_RANDOMIZED_SPINE_BATCH / item['path']) == item.get('sha256')
                    for item in linked
                )
                if (curriculum_index.get('schema') != 'dio.homs.curriculum.master_index.v1'
                        or curriculum_index.get('grade_count') != 12
                        or curriculum_index.get('grade_range') != [1, 12]
                        or curriculum_index.get('randomization_seed') != 20261101
                        or curriculum_index.get('batch_receipt_sha256') != digest_file(batch_receipt_path)
                        or curriculum_index.get('batch_execution_receipt_sha256') != digest_file(batch_execution_path)
                        or curriculum_index.get('caps_alignment_sha256') != digest_file(HOMS_QUESTION_CAPS_ALIGNMENT)
                        or curriculum_index.get('random_subject_assignment_sha256') != digest_file(ROOT / 'deliverables/homs_random_grade_exam_set_20261101/RANDOM_SUBJECT_ASSIGNMENTS.json')
                        or curriculum_index.get('human_curriculum_owner_review_required') is not True
                        or curriculum_index.get('term_fit_inferred') is not False
                        or curriculum_index.get('candidate_omissions_computed') is not False
                        or curriculum_index.get('professional_conclusion') is not False
                        or curriculum_index.get('release_authorized') is not False
                        or len(linked) != 60 or not linked_match
                        or curriculum_index.get('index', {}).get('sha256') != digest_file(HOMS_CURRICULUM_MASTER_INDEX)
                        or len(re.findall(r'<article class="grade">', curriculum_html)) != 12
                        or not all(token in curriculum_html for token in ('Filter grade or subject', 'CURRICULUM_REVIEW.html', 'CURRICULUM_PLAN_ENTRY_TEMPLATE.csv', 'Synthetic review cases', 'one blank term/topic row per exam question', 'Term fit and omission analysis are not computed'))):
                    raise ValueError('HOMS Curriculum master grade picker is stale, incomplete, or crossed its held review boundary')
                product_specific_refs.extend([
                    register(HOMS_CURRICULUM_MASTER_INDEX, curriculum_index.get('index', {}).get('sha256')),
                    register(HOMS_CURRICULUM_MASTER_INDEX_MANIFEST),
                    register(ROOT / 'scripts/build_homs_curriculum_master_index.py'),
                ])
                changes.append('The customer route now supports all twelve randomized grade/subject exam spines. The synthetic batch binds all five question-topic rows per grade to official CAPS PDF, alignment-map, exam and memo hashes (60 candidate rows total) and holds one deliberately mismatched topic per grade (12 review rows) for educator review. The grade picker also provides a source-bound CSV template with term/topic cells blank for customer plan entry.')
                limits = ['The 12-grade batch uses synthetic plan rows derived from the exam topic map. It validates source binding and candidate-match handling, not customer plan truth, complete CAPS coverage, term fit, curriculum adequacy, school compliance or approval. A curriculum owner must review actual complete school plans; classroom release remains unauthorized.']
                disposition = 'CURRENT_HELD_EXECUTION_VERIFIED'
            if product_specific_refs:
                changes.append('Current evidence includes question-level CAPS topic and page mappings for all twelve randomized grade papers; school plan alignment remains unverified until a curriculum owner reviews the approved plan.')
                if not HOMS_CURRICULUM_RANDOMIZED_SPINE_BATCH.is_dir():
                    limits = ['Current automated customer mapping covers Grade 8 Social Sciences. The controlled plan is synthetic and incomplete; this route does not compute omissions, prove plan truth/adequacy, confirm CAPS applicability, or grant school approval. A curriculum owner must review the approved complete plan.']
        if name == 'HOMS Learning Studio' and HOMS_EXAM_LEARNING_EVIDENCE.is_file():
            product_specific_refs.append(register(HOMS_EXAM_LEARNING_EVIDENCE))
            changes.append('A separate Grade 10 Physical Sciences exam spine is bound into the learning pack with hash-verified exam and memo artifacts; educator review and classroom release remain pending.')
        if name == 'HOMS Learning Studio' and HOMS_GRADE_CROSSWALKS.is_file():
            product_specific_refs.append(register(HOMS_GRADE_CROSSWALKS))
            changes.append('Twelve source-bound educator planning maps connect each randomized grade exam and memo to teaching checkpoints. The crosswalks do not claim full CAPS clause alignment.')
        if name == 'HOMS Learning Studio' and (HOMS_LEARNING_STUDIO_BATCH / 'HOMS_LEARNING_STUDIO_GRADE_BATCH_RECEIPT.json').is_file():
            batch_path = HOMS_LEARNING_STUDIO_BATCH / 'HOMS_LEARNING_STUDIO_GRADE_BATCH_RECEIPT.json'
            batch = read_json(batch_path)
            if batch.get('grade_count') != 12 or batch.get('all_grades_built') is not True:
                raise ValueError('HOMS Learning Studio batch receipt does not prove all twelve grade packs')
            if not HOMS_LEARNING_STUDIO_BATCH_AUDIT.is_file() or read_json(HOMS_LEARNING_STUDIO_BATCH_AUDIT).get('all_grade_sources_and_outputs_verified') is not True:
                raise ValueError('HOMS Learning Studio grade batch source/output audit is missing or did not pass')
            product_specific_refs.append(register(batch_path))
            product_specific_refs.append(register(HOMS_LEARNING_STUDIO_BATCH_AUDIT))
            disposition = 'CURRENT_HELD_EXECUTION_VERIFIED'
            changes.append('HOMS Learning Studio now renders a learner revision guide, educator lesson/marking map, paired exam and memo, video storyboard and review bundle for each of the twelve randomized grade spines. A grade-by-grade audit verified source exam/memo, random subject assignment, CAPS source, spine and all rendered file hashes. Every pack is held for educator approval; only an exact matching video asset can attach.')
            limits = ['The twelve packs are draft companions to the supplied exam/memo spines, not complete lesson sequences or proof of full CAPS coverage. Subject educators must confirm content, grade/term fit and classroom suitability; no exact matching video bundle was available for any of these grade scopes.']
            for grade_row in batch.get('grades', []):
                grade = int(grade_row['grade'])
                grade_root = HOMS_LEARNING_STUDIO_BATCH / f'grade-{grade:02d}'
                for file_row in grade_row.get('files', []):
                    path = HOMS_LEARNING_STUDIO_BATCH / file_row['path']
                    if path.is_file():
                        register(path, file_row.get('sha256'))
                preview = grade_root / 'index.html'
                if preview.is_file():
                    product_specific_refs.append(register(preview))
            if not HOMS_LEARNING_STUDIO_MASTER_INDEX.is_file() or not HOMS_LEARNING_STUDIO_MASTER_INDEX_MANIFEST.is_file():
                raise ValueError('HOMS Learning Studio master grade picker or its manifest is missing')
            index_manifest = read_json(HOMS_LEARNING_STUDIO_MASTER_INDEX_MANIFEST)
            assignment_manifest = ROOT / 'deliverables/homs_random_grade_exam_set_20261101/RANDOM_SUBJECT_ASSIGNMENTS.json'
            index_html = HOMS_LEARNING_STUDIO_MASTER_INDEX.read_text(encoding='utf-8')
            linked_outputs = index_manifest.get('linked_grade_outputs') or []
            linked_outputs_match = all(
                (HOMS_LEARNING_STUDIO_BATCH / item['path']).is_file()
                and digest_file(HOMS_LEARNING_STUDIO_BATCH / item['path']) == item.get('sha256')
                for item in linked_outputs
            )
            if (index_manifest.get('schema') != 'dio.homs.learning_studio.master_index.v1'
                    or index_manifest.get('grade_count') != 12
                    or index_manifest.get('grade_range') != [1, 12]
                    or index_manifest.get('random_seed') != 20261101
                    or index_manifest.get('batch_receipt_sha256') != digest_file(batch_path)
                    or index_manifest.get('batch_audit_sha256') != digest_file(HOMS_LEARNING_STUDIO_BATCH_AUDIT)
                    or index_manifest.get('assignment_manifest_sha256') != digest_file(assignment_manifest)
                    or index_manifest.get('classroom_release_authorized') is not False
                    or index_manifest.get('educator_approval_required') is not True
                    or len(linked_outputs) != 84 or not linked_outputs_match
                    or index_manifest.get('index', {}).get('sha256') != digest_file(HOMS_LEARNING_STUDIO_MASTER_INDEX)
                    or len(re.findall(r'<article class="grade-card">', index_html)) != 12
                    or not all(token in index_html for token in ('Filter by grade or subject', 'EDUCATOR_LESSON_PLANNER.html', 'Marking memo', 'Seed 20261101', 'Classroom release remains blocked'))):
                raise ValueError('HOMS Learning Studio master grade picker is stale, incomplete, or crossed its educator gate')
            product_specific_refs.extend([
                register(HOMS_LEARNING_STUDIO_MASTER_INDEX, index_manifest.get('index', {}).get('sha256')),
                register(HOMS_LEARNING_STUDIO_MASTER_INDEX_MANIFEST),
                register(ROOT / 'scripts/build_homs_learning_studio_master_index.py'),
            ])
        if name == 'HOMS Learning Studio' and HOMS_LEARNING_STUDIO_CUSTOMER_DEMO.is_dir():
            package_receipt_path = HOMS_LEARNING_STUDIO_CUSTOMER_DEMO / 'CUSTOMER_PACKAGE_RECEIPT.json'
            if package_receipt_path.is_file():
                package_receipt = read_json(package_receipt_path)
                for output in package_receipt.get('outputs', []):
                    output_path = HOMS_LEARNING_STUDIO_CUSTOMER_DEMO / output['path']
                    if output_path.is_file():
                        register(output_path, output.get('sha256'))
            for path in (HOMS_LEARNING_STUDIO_CUSTOMER_DEMO / 'CUSTOMER_PACKAGE_RECEIPT.json',
                         HOMS_LEARNING_STUDIO_CUSTOMER_DEMO / 'CUSTOMER_EXECUTION_RECEIPT.json',
                         HOMS_LEARNING_STUDIO_CUSTOMER_DEMO / 'learning_studio/index.html'):
                if path.is_file():
                    product_specific_refs.append(register(path))
            disposition = 'CURRENT_HELD_EXECUTION_VERIFIED'
            changes.append('The customer packet entry point accepts an explicit Grade 1–12 selection, validates the randomized exam/memo spine, and returns an educator-held pack; a Grade 1 customer-route execution is recorded.')
        if name == 'HOMS Learning Studio' and HOMS_LEARNING_STUDIO_CUSTOMER_GRADE_BATCH.is_dir():
            batch_path = HOMS_LEARNING_STUDIO_CUSTOMER_GRADE_BATCH / 'HOMS_LEARNING_STUDIO_CUSTOMER_GRADE_BATCH_RECEIPT.json'
            batch = read_json(batch_path)
            grade_rows = batch.get('results') or []
            if (len(grade_rows) != 12
                    or {int(row.get('grade') or 0) for row in grade_rows} != set(range(1, 13))
                    or batch.get('educator_approval_required') is not True
                    or batch.get('classroom_release_authorized') is not False):
                raise ValueError('HOMS Learning Studio customer batch must contain twelve educator-held grade packs')
            product_specific_refs.append(register(batch_path))
            for grade_row in grade_rows:
                product_specific_refs.append(register(
                    HOMS_LEARNING_STUDIO_CUSTOMER_GRADE_BATCH / grade_row['package_receipt'],
                    grade_row['package_receipt_sha256'],
                ))
                product_specific_refs.append(register(
                    HOMS_LEARNING_STUDIO_CUSTOMER_GRADE_BATCH / grade_row['execution_receipt'],
                    grade_row['execution_receipt_sha256'],
                ))
                grade_dir = HOMS_LEARNING_STUDIO_CUSTOMER_GRADE_BATCH / f"grade-{int(grade_row['grade']):02d}"
                learning_root = grade_dir / 'learning_studio'
                learning_manifest = read_json(learning_root / 'HOMS_LEARNING_STUDIO_MANIFEST.json')
                planner = learning_manifest.get('educator_planner') or {}
                planner_path = learning_root / str(planner.get('path') or '')
                planner_receipt_row = next((item for item in grade_row.get('outputs') or []
                                            if item.get('path') == grade_row.get('educator_planner_path')), None)
                planner_validation = (learning_manifest.get('validation') or {}).get('interactive_educator_planner') or {}
                planner_html = planner_path.read_text(encoding='utf-8') if planner_path.is_file() else ''
                if (not planner_receipt_row or not planner_path.is_file()
                        or planner_receipt_row.get('sha256') != digest_file(planner_path)
                        or grade_row.get('educator_planner_sha256') != digest_file(planner_path)
                        or planner.get('sha256') != digest_file(planner_path)
                        or planner.get('source_spine_sha256') != grade_row.get('source_spine_sha256')
                        or planner.get('question_count') != grade_row.get('educator_planner_question_count')
                        or planner.get('planning_fields_per_question') != 7
                        or planner_validation.get('all_fields_initially_blank') is not True
                        or planner_validation.get('classroom_release_authorized') is not False
                        or planner_html.count("data-field='") != grade_row.get('educator_planner_question_count', 0) * 7
                        or 'localStorage' not in planner_html or 'Download lesson-plan JSON' not in planner_html):
                    raise ValueError(f"HOMS Learning Studio Grade {grade_row['grade']} interactive educator planner is stale or not source-bound")
                for output in grade_row.get('outputs') or []:
                    product_specific_refs.append(register(grade_dir / output['path'], output.get('sha256')))
            changes.append('Each randomized Grade 1–12 customer pack now includes a source-bound interactive educator lesson planner with seven blank planning fields per assessment question, local browser save/resume, and JSON download. The 12 synthetic customer routes bind the planner to the same question spine as the learner guide, educator map, exam/memo PDFs and Pictora visual; release remains held.')
            limits = ['The planner supplies workflow fields, not lesson content or curriculum approval. Educators must complete and review the plan, confirm prerequisite instruction, examples, formative checks, differentiation, term fit, assessment validity and memo accuracy. Browser drafts are local and optional; educator approval and classroom release remain unrecorded and unauthorized.']
            disposition = 'CURRENT_HELD_EXECUTION_VERIFIED'
        if name == 'Document Studio Localize' and DOCUMENT_STUDIO_LOCALIZE_FOLLOWUP.is_file():
            product_specific_refs.append(register(DOCUMENT_STUDIO_LOCALIZE_FOLLOWUP))
            changes.append('Native Afrikaans processing treats unapproved machine glossary alternatives as advisory and accepts an English source phrase when its Afrikaans equivalent is explicitly paired. The earlier P6 diagnostic is retained as historical evidence; the latest route applies a bounded double-negation repair and still requires a proficient reviewer.')
            changes.append('An opt-in local critic hallucinated an unrelated long paragraph from the short “Draft section” heading; the new scope-expansion guard rejects that revision. Critic revisions remain disabled by default.')
            limits = ['The latest draft corrects the single detected double-negation defect, but the full Afrikaans translation still requires review by a proficient language reviewer; linguistic approval and release remain blocked.']
        if name == 'Document Studio Localize' and DOCUMENT_STUDIO_LOCALIZE_CUSTOMER_DEMO.is_dir():
            execution_path = DOCUMENT_STUDIO_LOCALIZE_CUSTOMER_DEMO / 'CUSTOMER_EXECUTION_RECEIPT.json'
            if execution_path.is_file():
                execution = read_json(execution_path)
                receipt = execution.get('receipt') or {}
                processing = receipt.get('processing') or {}
                release = receipt.get('release') or {}
                if processing.get('local_validation_passed') is not True or processing.get('language_review_flags_present') is not False or release.get('linguistic_quality_approved') is not False or release.get('delivery_released') is not False:
                    raise ValueError('Document Studio Localize latest customer execution did not preserve its language-review and release holds')
                product_specific_refs.append(register(execution_path))
                if DOCUMENT_STUDIO_LOCALIZE_REVIEW_HANDOFF.is_file():
                    product_specific_refs.append(register(DOCUMENT_STUDIO_LOCALIZE_REVIEW_HANDOFF))
                workspace_receipt = read_json(DOCUMENT_STUDIO_LOCALIZE_REVIEW_WORKSPACE_RECEIPT)
                workspace_html = DOCUMENT_STUDIO_LOCALIZE_REVIEW_WORKSPACE.read_text(encoding='utf-8')
                if (workspace_receipt.get('schema') != 'dio.document_studio_localize.afrikaans_review_workspace.v1'
                        or workspace_receipt.get('execution') != DOCUMENT_STUDIO_LOCALIZE_CUSTOMER_DEMO.name
                        or workspace_receipt.get('segment_count') != 8
                        or workspace_receipt.get('terminology_row_count') != 2
                        or workspace_receipt.get('linguistic_quality_approved') is not False
                        or workspace_receipt.get('delivery_released') is not False
                        or workspace_receipt.get('release_authorized') is not False
                        or any((workspace_receipt.get('features') or {}).get(key) is not expected for key, expected in {
                            'side_by_side_source_target': True, 'segment_search': True, 'pending_only_filter': True,
                            'reviewer_proficiency_declaration': True, 'term_adjudication': True,
                            'duplicate_term_reconciliation_gate': True,
                            'draft_download_and_resume': True, 'draft_context_binds_source_target_and_glossary': True,
                            'browser_storage_used': False, 'network_requests': False,
                        }.items())
                        or 'localStorage' in workspace_html or 'fetch(' in workspace_html
                        or 'Download review draft JSON' not in workspace_html
                        or 'Resume matching draft' not in workspace_html
                        or 'reviewer reports all required fields complete' not in workspace_html
                        or workspace_receipt.get('input_sha256', {}).get('current_workspace_sha256') != digest_file(DOCUMENT_STUDIO_LOCALIZE_REVIEW_WORKSPACE)
                        or workspace_receipt.get('input_sha256', {}).get('template_sha256') != digest_file(DOCUMENT_STUDIO_LOCALIZE_CUSTOMER_DEMO / 'document_studio/DIO_LOCALIZE_V6/LINGUA_HUMAN_REVIEW_TEMPLATE.json')
                        or workspace_receipt.get('input_sha256', {}).get('hash_bound_handoff_sha256') != digest_file(DOCUMENT_STUDIO_LOCALIZE_REVIEW_HANDOFF)
                        or workspace_receipt.get('input_sha256', {}).get('glossary_sha256') != digest_file(DOCUMENT_STUDIO_LOCALIZE_CUSTOMER_DEMO / 'document_studio/DIO_LOCALIZE_V6/TERMINOLOGY_GLOSSARY.csv')):
                    raise ValueError('Document Studio Localize Afrikaans review workspace lost source binding, reviewer workflow, or release hold')
                product_specific_refs.extend([register(DOCUMENT_STUDIO_LOCALIZE_REVIEW_WORKSPACE),
                                              register(DOCUMENT_STUDIO_LOCALIZE_REVIEW_WORKSPACE_RECEIPT),
                                              register(ROOT / 'scripts/build_document_studio_localize_review_workspace.py')])
                for artifact_row in execution.get('artifacts') or []:
                    product_specific_refs.append(register(DOCUMENT_STUDIO_LOCALIZE_CUSTOMER_DEMO / artifact_row['path'], artifact_row.get('sha256')))
                changes.append('The latest full customer route applies a provenance-recorded, single-sentence Afrikaans double-negation repair to P6. A new segment-level reviewer handoff hashes both source and target text, asks the reviewer to declare language proficiency, and keeps release blocked until human review is complete.')
                changes.append('The Afrikaans handoff now presents all eight source/target segments side by side, includes terminology decisions for both machine glossary rows, supports unresolved-only filtering, and saves/restores reviewer drafts bound to source, target, glossary and execution hashes. No browser storage or network requests are used; edited text still needs re-rendering and a separate review before delivery.')
                limits = ['The negation repair resolves the detected syntax diagnostic only; it does not establish fluency, semantic accuracy, approved terminology, or publication readiness. Proficient Afrikaans review remains required and delivery remains blocked.']
        if name == 'Document Studio Localize' and DOCUMENT_STUDIO_LOCALIZE_SEMANTIC_DEMO.is_dir():
            customer_root = DOCUMENT_STUDIO_LOCALIZE_SEMANTIC_DEMO / 'document-studio-localize/document-studio-localize'
            execution_path = customer_root / 'PROFESSIONAL_EVIDENCE_RECEIPT.json'
            job_root = customer_root / 'EXECUTION/document_studio/PRO-DOCUMENT_STUDIO_LOCALIZE'
            execution = read_json(execution_path)
            document_receipt = read_json(job_root / 'DOCUMENT_STUDIO_RECEIPT.json')
            processing = document_receipt.get('processing') or {}
            release = document_receipt.get('release') or {}
            qa = read_json(job_root / 'DOCUMENT_STUDIO_QA.json')
            lingua_qa = read_json(job_root / 'LINGUA_QA.json')
            semantic = read_json(job_root / 'LINGUA_SEMANTIC_OBJECT.json')
            human_template = read_json(job_root / 'LINGUA_HUMAN_REVIEW_TEMPLATE.json')
            translation = (semantic.get('translations') or {}).get('Afrikaans') or {}
            target_units = {row.get('unit_id'): row.get('target_text') for row in translation.get('units') or []}
            expected_targets = {
                'P2': 'Die nota verduidelik die prosedures vir kliniekafsprake en bevat verskeie beskermde programname.',
                'P7': '## Konsepafdeling',
            }
            if (execution.get('status') != 'PASS_FULL_PIPELINE'
                    or processing.get('local_validation_passed') is not True
                    or release.get('linguistic_quality_approved') is not False
                    or release.get('delivery_released') is not False
                    or qa.get('linguistic_quality_approved') is not False
                    or lingua_qa.get('linguistic_quality_approved') is not False
                    or lingua_qa.get('review_required') is not True
                    or any(target_units.get(key) != value for key, value in expected_targets.items())
                    or human_template.get('approval_state') != 'pending'
                    or any(row.get('approved') is not False for row in human_template.get('units') or [])):
                raise ValueError('Document Studio Localize semantic repair evidence failed its output or human-approval boundary')
            p8_source = next((row.get('source_text') for row in (semantic.get('source') or {}).get('units') or [] if row.get('unit_id') == 'P8'), '')
            p8_target = target_units.get('P8') or ''
            if ('however the wording and heading structure are inconsistent' not in p8_source
                    or 'maar die bewoording en opskrifstruktuur is inkonsekwent' not in p8_target):
                raise ValueError('Document Studio Localize did not preserve the targeted contrast meaning in the current source/target pair')
            for path in [execution_path,
                         customer_root / 'CUSTOMER_PACKET/CUSTOMER_PACKET_MANIFEST.json',
                         job_root / 'DOCUMENT_STUDIO_QA.json', job_root / 'LINGUA_QA.json',
                         job_root / 'LINGUA_SEMANTIC_OBJECT.json', job_root / 'LINGUA_HUMAN_REVIEW_TEMPLATE.json',
                         job_root / 'BILINGUAL_REVIEW_COPY.docx', job_root / 'HUMAN_APPROVAL.md',
                         job_root / 'formatted/Afrikaans/lingua-pro-document-studio-localize-afrikaans.pdf',
                         job_root / 'formatted/Afrikaans/lingua-pro-document-studio-localize-afrikaans.html']:
                if path.is_file():
                    product_specific_refs.append(register(path))
            changes.append('A scoped, machine-proposed Afrikaans phrase set corrected the synthetic review-copy sentence for “however,” removed the P2 English compound leak, and translated “Draft section” as “Konsepafdeling.” The catalog route passed; exact source/target text hashes, pending human review, and blocked release are retained.')
            limits = ['Phrase corrections remain unapproved machine proposals. A proficient Afrikaans reviewer must review the complete document and approve the glossary; the route’s integrity pass does not establish fluency, and delivery remains blocked.']
        if current:
            disposition = 'CURRENT_HELD_EXECUTION_VERIFIED' if current['all_variants_verified'] else 'CURRENT_INPUT_GAP_REFUSED'
        if name.startswith('Sophia '):
            changes.append('Current held diagnostic preparation replaces the earlier setup block; strict complete constitutional approval is not established.')
            limits = ['Source-grounded engineering drafts require academic review. Tutor prepares practice; completed teaching or learning gains are not proved.']
        if name == 'Document Studio Localize':
            changes.append('Current three-variant local MT packaging execution supersedes the earlier execution state.')
            if not DOCUMENT_STUDIO_LOCALIZE_FOLLOWUP.is_file() and not DOCUMENT_STUDIO_LOCALIZE_CUSTOMER_DEMO.is_dir():
                limits = ['Actual Afrikaans review found semantic and grammatical faults; proficient language approval is pending. Excluded from the twelve pilot candidates.']
        if name == 'Finance Readiness Studio' and (OUTPUT / 'FINANCE_READINESS_STUDIO_RECONCILIATION_20261101_V2').is_dir():
            changes.append('Current customer route binds the funding request and itemized uses to source records, calculates their arithmetic variance, and retains lender and affordability decisions for human review.')
        if name in {'PromotionProof', 'CPDProof'}:
            changes.append('Current full-pipeline execution passes on a packet with explicitly declared review periods; source mappings remain zero accepted, so customer records and professional review are still required.')
            attached_batch = OUTPUT / ('CPDPROOF_SOURCE_ATTACHED_REVIEW_20261101_V3' if name == 'CPDProof' else 'PROMOTIONPROOF_ATTACHMENT_BINDING_DEMO_20261101_V3')
            if attached_batch.is_dir():
                changes.append('The customer review pack now carries manifest-bound source attachment paths and SHA-256 values alongside each cited register row; attachment content remains unvalidated and untrusted.')
            limits = ['Synthetic route execution does not establish actual CPD credits or promotion readiness. Map actual dated source records and obtain professional review; no promotion or CPD approval.']
        if key:
            disposition = 'BOUNDED_PAID_PILOT_CANDIDATE_HUMAN_REVIEW_REQUIRED'
            limits = [capabilities[key]['limit']]
            changes.append('Source-driven customer preparation artifacts supplement the historical fixture assessment; operator pilot qualification is provisional.')
            if name in {'VAMP Performance', 'Evidex EvidenceOps'}:
                changes.append('Current native execution and customer source-record deliverables are retained separately from historical runs.')
        if name == 'Document Studio Localize' and DOCUMENT_STUDIO_LOCALIZE_SEMANTIC_DEMO.is_dir():
            limits = ['The current synthetic draft corrects the observed phrase-level semantic and terminology defects, but glossary terms are unapproved machine proposals. A proficient Afrikaans reviewer must assess the complete translation; linguistic approval and delivery remain blocked.']
        if name == 'Evidex EvidenceOps' and EVIDEX_SCOPE_COMPARABILITY_DEMO.is_dir():
            evidence_path = EVIDEX_SCOPE_COMPARABILITY_DEMO / 'EVIDEX_SCOPE_COMPARABILITY_EXECUTION_EVIDENCE.json'
            review_path = EVIDEX_SCOPE_COMPARABILITY_DEMO / 'CUSTOMER_EVIDENCE_REVIEW.json'
            package_path = EVIDEX_SCOPE_COMPARABILITY_DEMO / 'CUSTOMER_PACKAGE_RECEIPT.json'
            execution_path = EVIDEX_SCOPE_COMPARABILITY_DEMO / 'CUSTOMER_EXECUTION_RECEIPT.json'
            evidence, review = map(read_json, (evidence_path, review_path))
            mismatch_request = next((row for row in review.get('review_actions', [])
                                     if row.get('record_id') == 'register-mismatch' and row.get('reason') == 'QUANTITY_RECONCILIATION'), {})
            unknown_request = next((row for row in review.get('review_actions', [])
                                    if row.get('record_id') == 'register-unknown' and row.get('reason') == 'QUANTITY_RECONCILIATION'), {})
            mismatch_comparison = next((row for row in review.get('quantity_comparisons', [])
                                        if row.get('candidate_record_id') == 'register-mismatch'), {})
            unknown_comparison = next((row for row in review.get('quantity_comparisons', [])
                                       if row.get('candidate_record_id') == 'register-unknown'), {})
            evidence_requests_path = EVIDEX_SCOPE_COMPARABILITY_DEMO / 'EVIDENCE_REQUESTS.csv'
            if (evidence.get('schema') != 'dio.evidex.scope_comparability_execution.v1'
                    or evidence.get('review_sha256') != hashlib.sha256(review_path.read_bytes()).hexdigest()
                    or evidence.get('source_count') != 4
                    or evidence.get('comparison_count') != 3
                    or evidence.get('declared_scope_match_count') != 1
                    or evidence.get('noncomparable_record_count') != 2
                    or mismatch_comparison.get('difference') is not None
                    or mismatch_comparison.get('difference_basis') is not None
                    or mismatch_comparison.get('state') != 'DECLARED_SCOPE_INCOMPARABLE_REVIEW_REQUIRED'
                    or unknown_comparison.get('difference') is not None
                    or unknown_comparison.get('difference_basis') is not None
                    or unknown_comparison.get('state') != 'DECLARED_SCOPE_INCOMPARABLE_REVIEW_REQUIRED'
                    or evidence.get('evidence_request_count') != len(review.get('review_actions', []))
                    or evidence.get('evidence_requests_sha256') != hashlib.sha256(evidence_requests_path.read_bytes()).hexdigest()
                    or not any('coverage start and end dates' in field for field in mismatch_request.get('requested_evidence', []))
                    or not any('population/program identifier' in field for field in mismatch_request.get('requested_evidence', []))
                    or not any('coverage start and end dates' in field for field in unknown_request.get('requested_evidence', []))
                    or not any('population/program identifier' in field for field in unknown_request.get('requested_evidence', []))
                    or review.get('support_adjudicated') is not False
                    or review.get('release_authorized') is not False
                    or evidence.get('customer_package_sha256') != hashlib.sha256(package_path.read_bytes()).hexdigest()
                    or evidence.get('customer_execution_sha256') != hashlib.sha256(execution_path.read_bytes()).hexdigest()):
                raise ValueError('Evidex scope-comparability evidence did not preserve declared-scope matching and unverified status')
            for path in sorted(EVIDEX_SCOPE_COMPARABILITY_DEMO.rglob('*')):
                if path.is_file():
                    product_specific_refs.append(register(path))
            for relative in ('products/evidex_customer_review.py', 'products/evidex_studio_finish.py', 'products/customer_specialist_pathways.py',
                             'scripts/run_evidex_scope_comparability_demo.py'):
                product_specific_refs.append(register(ROOT / relative))
            changes.append('Evidex binds candidate quantity comparisons to declared date ranges and populations and exports an evidence-request worksheet that names the original record, custodian, record location, row-level quantity basis and missing or conflicting scope fields. It now withholds arithmetic differences for two records with mismatched or missing scope; only the matching-scope 10-versus-9 difference is calculated, and it remains unverified.')
            limits.append('Scope and population values are customer-declared and unverified. Exact metadata matches do not authenticate records or prove delivery; requested fields guide review and do not independently reconcile quantities.')
        if name == 'Evidex EvidenceOps' and EVIDEX_ATTACHED_SOURCE_DEMO.is_dir():
            evidence_path = EVIDEX_ATTACHED_SOURCE_DEMO.parent / 'EVIDEX_ATTACHED_SOURCE_DEMO_20261102_V1.json'
            manifest_path = EVIDEX_ATTACHED_SOURCE_DEMO / 'EVIDEX_SOURCE_FILE_MANIFEST.json'
            execution_path = EVIDEX_ATTACHED_SOURCE_DEMO / 'CUSTOMER_EXECUTION_RECEIPT.json'
            evidence, manifest, execution = map(read_json, (evidence_path, manifest_path, execution_path))
            if (evidence.get('schema') != 'dio.evidex.attached_source_execution.v1'
                    or evidence.get('attachment_count') != 3 or manifest.get('file_count') != 3
                    or evidence.get('all_output_hashes_verified') is not True
                    or manifest.get('source_authenticity_verified') is not False
                    or execution.get('release_authorized') is not False
                    or execution.get('external_effects') is not False):
                raise ValueError('Evidex attached-file review lost its original-file or held-review boundary')
            product_specific_refs.extend([register(evidence_path), register(manifest_path), register(execution_path),
                                          register(ROOT / 'scripts/run_evidex_attached_source_demo.py')])
            for item in manifest.get('files') or []:
                raw_path = EVIDEX_ATTACHED_SOURCE_DEMO / item['path']
                if hashlib.sha256(raw_path.read_bytes()).hexdigest() != item.get('sha256'):
                    raise ValueError(f"Evidex source file hash mismatch: {item.get('source_id')}")
                product_specific_refs.append(register(raw_path, item.get('sha256')))
            changes.append('Evidex now accepts original UTF-8 text and CSV attachments, preserves the uploaded bytes, and records separate hashes for each original file and extracted text. The generated review quotes customer-supplied statements and requests reconciliation, while source authenticity and support remain explicitly unverified.')
            limits.append('Attachment hashing and text extraction do not authenticate the sender, establish document truth, verify row completeness or adjudicate support. A reviewer must inspect original records and resolve each discrepancy; no outcome or release is certified.')
        if name == 'Article Publication Studio' and article_byte_receipt.is_file():
            binding_receipt = read_json(article_byte_receipt)
            changes.append('Article Publication Studio now joins each draft claim to the exact customer evidence-register row using UTF-8 byte spans, source-file/row/statement SHA-256 values, and the native proof fingerprint. Claims remain explicitly unverified customer assertions; rights, privacy, attribution and publication reviews stay pending.')
            limits.append('Byte-accurate source binding verifies where a customer assertion came from, not whether it is true, independently sourced, licensed or suitable for publication. Human editorial and rights review remain required.')
        if name == 'Article Publication Studio' and ARTICLE_PUBLICATION_STUDIO_EDITORIAL_DEMO.is_dir():
            evidence_path = ARTICLE_PUBLICATION_STUDIO_EDITORIAL_DEMO / 'EDITORIAL_REVIEW_SURFACE_EVIDENCE.json'
            case_root = ARTICLE_PUBLICATION_STUDIO_EDITORIAL_DEMO / 'article-publication-studio/article-publication-studio'
            receipt_path = case_root / 'PROFESSIONAL_EVIDENCE_RECEIPT.json'
            worksheet_path = case_root / 'EXECUTION/EDITORIAL_REVIEW_WORKSHEET.csv'
            guide_path = case_root / 'EXECUTION/EDITORIAL_REVIEW_GUIDE.md'
            source_register_path = case_root / 'CUSTOMER_PACKET/SOURCES/02_evidence_register.csv'
            review_html_path = case_root / 'EDITORIAL_REVIEW.html'
            validation_path = ARTICLE_PUBLICATION_STUDIO_EDITORIAL_DEMO / 'EDITORIAL_REVIEW_VALIDATION.json'
            evidence, case_receipt = read_json(evidence_path), read_json(receipt_path)
            validation = read_json(validation_path)
            worksheet_rows = list(csv.DictReader(worksheet_path.open(encoding='utf-8', newline='')))
            if (evidence.get('schema') != 'dio.article_publication_studio.editorial_review_surface_evidence.v1'
                    or evidence.get('professional_evidence_receipt_sha256') != hashlib.sha256(receipt_path.read_bytes()).hexdigest()
                    or evidence.get('worksheet_sha256') != hashlib.sha256(worksheet_path.read_bytes()).hexdigest()
                    or evidence.get('review_html_sha256') != hashlib.sha256(review_html_path.read_bytes()).hexdigest()
                    or 'output.push(row)' in review_html_path.read_text(encoding='utf-8')
                    or 'const output=currentRows()' not in review_html_path.read_text(encoding='utf-8')
                    or evidence.get('validation_receipt_sha256') != hashlib.sha256(validation_path.read_bytes()).hexdigest()
                    or validation.get('state') != 'REVIEW_INCOMPLETE_OR_HOLD_REQUIRED'
                    or validation.get('source_register_sha256') != hashlib.sha256(source_register_path.read_bytes()).hexdigest()
                    or validation.get('expected_claim_count') != len(worksheet_rows)
                    or any(str(issue.get('code') or '').startswith('SOURCE_')
                           or issue.get('code') in {'DUPLICATE_WORKSHEET_HEADER', 'WORKSHEET_ROW_HAS_EXTRA_FIELDS'}
                           for issue in validation.get('issues') or [])
                    or validation.get('publication_authorized') is not False
                    or not validation.get('issues')
                    or not worksheet_rows or evidence.get('claim_count') != len(worksheet_rows)
                    or evidence.get('review_drafts_downloadable_and_reopenable') is not True
                    or evidence.get('drafts_remain_local_until_user_exports_a_file') is not True
                    or evidence.get('draft_import_checks_source_binding_fingerprint_and_claim_ids') is not True
                    or evidence.get('draft_source_bindings_sha256') != hashlib.sha256((case_root / 'EXECUTION/EDITORIAL_CLAIM_SOURCE_BINDINGS.csv').read_bytes()).hexdigest()
                    or any(row.get('editorial_decision') != 'PENDING' or row.get('source_authenticity_decision') != 'PENDING'
                           or row.get('rights_and_permission_decision') != 'PENDING' for row in worksheet_rows)
                    or any(not row.get('source_row_sha256') for row in worksheet_rows)
                    or case_receipt.get('external_publication') != 'REFUSE'
                    or case_receipt.get('authority_created') is not False):
                raise ValueError('Article Publication Studio editorial worksheet did not retain source-bound pending decisions and publication hold')
            product_specific_refs.extend([register(evidence_path), register(receipt_path), register(worksheet_path), register(guide_path), register(review_html_path), register(validation_path), register(source_register_path), register(ROOT / 'scripts/run_article_publication_studio_editorial_surface.py'), register(ROOT / 'scripts/validate_article_publication_editorial_review.py')])
            changes.append('Article Publication Studio now carries each source-row hash through the editor export, then rechecks the original packet CSV file hash, exact byte span, row hash, record ID and statement before validating reviewer decisions. The blank worksheet fails closed against current packet bytes; local drafts remain source-bound, and publication remains refused.')
            limits.append('The validator confirms packet row identity and worksheet completeness only. It does not authenticate a source, establish claim truth, rights, privacy, attribution or reviewer competence and cannot authorize publication; separate publication authority remains required.')
        if name in {'Professional Correspondence', 'Professional Correspondence Studio'} and CORRESPONDENCE_REVIEW_VALIDATION_DEMO.is_dir():
            evidence_path = CORRESPONDENCE_REVIEW_VALIDATION_DEMO / 'CORRESPONDENCE_REVIEW_VALIDATION_EVIDENCE.json'
            evidence = read_json(evidence_path)
            product_run = next((row for row in evidence.get('products') or [] if row.get('product_name') == name), None)
            if not product_run:
                raise ValueError(f'{name} controlled correspondence review evidence is missing')
            folder = 'professional-correspondence' if name == 'Professional Correspondence' else 'professional-correspondence-studio'
            run_dir = CORRESPONDENCE_REVIEW_VALIDATION_DEMO / folder
            worksheet_path = run_dir / 'CORRESPONDENCE_EDITOR_REVIEW.csv'
            bindings_path = run_dir / 'CORRESPONDENCE_SOURCE_BYTE_BINDINGS.json'
            guide_path = run_dir / 'CORRESPONDENCE_EDITOR_REVIEW_GUIDE.md'
            review_html_path = run_dir / 'CORRESPONDENCE_EDITOR_REVIEW.html'
            validation_path = run_dir / 'CORRESPONDENCE_EDITOR_REVIEW_VALIDATION.json'
            package_path = run_dir / 'CUSTOMER_PACKAGE_RECEIPT.json'
            validation = read_json(validation_path)
            with worksheet_path.open(encoding='utf-8', newline='') as handle:
                review_rows = list(csv.DictReader(handle))
            if (evidence.get('schema') != 'dio.professional_correspondence.review_validation_evidence.v1'
                    or evidence.get('all_blank_reviews_held') is not True
                    or evidence.get('all_send_authority_false') is not True
                    or product_run.get('validation_state') != 'REVIEW_INCOMPLETE_OR_HOLD_REQUIRED'
                    or product_run.get('send_authorized') is not False
                    or product_run.get('worksheet_sha256') != hashlib.sha256(worksheet_path.read_bytes()).hexdigest()
                    or product_run.get('bindings_sha256') != hashlib.sha256(bindings_path.read_bytes()).hexdigest()
                    or product_run.get('review_html_sha256') != hashlib.sha256(review_html_path.read_bytes()).hexdigest()
                    or product_run.get('customer_package_sha256') != hashlib.sha256(package_path.read_bytes()).hexdigest()
                    or validation.get('send_authorized') is not False
                    or validation.get('state') != 'REVIEW_INCOMPLETE_OR_HOLD_REQUIRED'
                    or not review_rows or sum(row.get('item_type') == 'requested_action' for row in review_rows) != 1
                    or read_json(package_path).get('external_send_authorized') is not False):
                raise ValueError(f'{name} editorial handoff did not retain source binding and no-send boundary')
            product_specific_refs.extend([register(evidence_path), register(package_path), register(worksheet_path), register(bindings_path), register(guide_path), register(review_html_path), register(validation_path), register(ROOT / 'scripts/validate_correspondence_editorial_review.py'), register(ROOT / 'scripts/run_correspondence_review_validation_demo.py'), register(ROOT / 'products/customer_specialist_pathways.py')])
            changes.append('The correspondence route now includes an offline sender/editor review page showing exact source text, editable proposed wording, decision controls and completed CSV export. The source-fact validator checks record identity and reviewer fields; blank decisions remain held, and sending is never authorized.')
            limits.append('The correspondence validator checks worksheet completeness and source-text identity only. It does not verify facts or legal positions; the named sender must decide tone, commitments and whether to send.')
        if name == 'FundingFinder' and FUNDING_FINDER_LIVE_REFRESH.is_file():
            live = read_json(FUNDING_FINDER_LIVE_REFRESH)
            scenarios = live.get('scenarios') or []
            if (live.get('status') != 'LIVE_OFFICIAL_SOURCES_CAPTURED_PIPELINE_QA_PASSED_PRODUCT_QUALIFICATION_UNPROVED'
                    or live.get('as_of') != '2026-11-04' or len(scenarios) != 3
                    or sum(len(row.get('opportunities') or []) for row in scenarios) != 5
                    or any(row.get('qa_passed') is not True or row.get('applicant_synthetic') is not True for row in scenarios)):
                raise ValueError('FundingFinder current-source refresh evidence is incomplete or overclaims applicant/eligibility results')
            if any(opportunity.get('fit_state') == 'appears_aligned_on_supplied_record'
                   for scenario in scenarios if scenario['scenario'].startswith('south-africa-')
                   for opportunity in scenario.get('opportunities') or []):
                raise ValueError('FundingFinder synthetic South African source cases must not be promoted to apparent eligibility')
            uk_case = next((row for row in scenarios if row.get('scenario') == 'uk-jurisdiction-mismatch-live'), None)
            if not uk_case or not any(row.get('id') == 'UK-LOTTERY' and row.get('fit_state') == 'mismatch_on_supplied_record'
                                      for row in uk_case.get('opportunities') or []):
                raise ValueError('FundingFinder UK jurisdiction mismatch evidence is missing')
            product_specific_refs.append(register(FUNDING_FINDER_LIVE_REFRESH))
            for artifact_row in live.get('artifact_index') or []:
                product_specific_refs.append(register(ROOT / artifact_row['path'], artifact_row.get('sha256')))
            changes.append('FundingFinder now binds a fresh official-source refresh to the customer route and decomposes NYDA screening into citizenship, residence, age minimum, age maximum and turnover checks. Retrieval bytes, source registers, eligibility matrices, customer reports and offline replay packets are hash-checked; pipeline QA passed while eligibility/timing remains unknown or mismatched and applicant records remain synthetic.')
            limits.append('Fresh source retrieval and source-bound pipeline QA do not prove current application availability, full-rule coverage, customer eligibility, funding decisions or buyer acceptance; confirm with each funder.')
        if name == 'FundingFinder' and FUNDING_FINDER_LIVE_CUSTOMER_ROUTE.is_dir():
            execution_path = FUNDING_FINDER_LIVE_CUSTOMER_ROUTE / 'CUSTOMER_EXECUTION_RECEIPT.json'
            execution = read_json(execution_path)
            receipt = execution.get('receipt') or {}
            shortlist = receipt.get('shortlist') or []
            canonical_packet_sha = hashlib.sha256(json.dumps(read_json(FUNDING_FINDER_LIVE_CUSTOMER_PACKET), sort_keys=True, ensure_ascii=False, separators=(',', ':')).encode()).hexdigest()
            if (execution.get('requested_product') != 'FundingFinder'
                    or execution.get('customer_packet_sha256') != canonical_packet_sha
                    or execution.get('human_review_required') is not True
                    or execution.get('release_authorized') is not False
                    or execution.get('external_effects') is not False
                    or execution.get('commercial_validation') != 'UNPROVED'
                    or receipt.get('as_of') != '2026-11-04'
                    or receipt.get('processing', {}).get('public_fetch_enabled') is not False
                    or receipt.get('release', {}).get('eligibility_certified') is not False
                    or receipt.get('release', {}).get('application_submitted') is not False
                    or len(shortlist) != 2
                    or any(row.get('fit_state') != 'unknown_review_required' or row.get('timing_state') != 'unknown' for row in shortlist)):
                raise ValueError('FundingFinder live-source catalog customer route failed its source/hash or held-output contract')
            product_specific_refs.extend([register(FUNDING_FINDER_LIVE_CUSTOMER_PACKET), register(execution_path)])
            for artifact_row in execution.get('artifacts') or []:
                product_specific_refs.append(register(FUNDING_FINDER_LIVE_CUSTOMER_ROUTE / artifact_row['path'], artifact_row.get('sha256')))
            changes.append('The fresh official-source snapshots were then passed through the catalog FundingFinder customer route as an offline, synthetic-applicant case. The route returned two NYDA/TIA opportunities with eligibility and timing still unknown, verified its generated artifact hashes, and kept application, eligibility certification, external effects and commercial qualification disabled.')
            limits.append('This is a synthetic applicant demonstration, not customer acceptance or an eligibility opinion; live availability and complete rules still require funder confirmation.')
        if name == 'FundingFinder' and FUNDING_FINDER_SERVICESETA_ROUTE.is_dir():
            evidence_path = FUNDING_FINDER_SERVICESETA_EVIDENCE
            execution_path = FUNDING_FINDER_SERVICESETA_ROUTE / 'CUSTOMER_EXECUTION_RECEIPT.json'
            evidence = read_json(evidence_path)
            execution = read_json(execution_path)
            receipt = execution.get('receipt') or {}
            shortlist = receipt.get('shortlist') or []
            source_path = FUNDING_FINDER_SERVICESETA_ROUTE / 'sources/SERVICES-SETA-DG-2026-27-03.raw'
            source_sha = hashlib.sha256(source_path.read_bytes()).hexdigest() if source_path.is_file() else None
            packet_hash = hashlib.sha256(FUNDING_FINDER_SERVICESETA_PACKET.read_bytes()).hexdigest()
            if (evidence.get('schema') != 'dio.fundingfinder.services_seta_customer_route_evidence.v1'
                    or evidence.get('as_of') != '2026-11-04'
                    or evidence.get('packet_sha256') != packet_hash
                    or evidence.get('customer_is_synthetic') is not True
                    or evidence.get('product_qualification') != 'UNPROVED'
                    or execution.get('requested_product') != 'FundingFinder'
                    or execution.get('customer_packet_sha256') != hashlib.sha256(json.dumps(read_json(FUNDING_FINDER_SERVICESETA_PACKET), sort_keys=True, ensure_ascii=False, separators=(',', ':')).encode()).hexdigest()
                    or execution.get('human_review_required') is not True
                    or execution.get('release_authorized') is not False
                    or execution.get('external_effects') is not False
                    or execution.get('commercial_validation') != 'UNPROVED'
                    or receipt.get('as_of') != '2026-11-04'
                    or receipt.get('processing', {}).get('public_fetch_enabled') is not True
                    or receipt.get('release', {}).get('eligibility_certified') is not False
                    or receipt.get('release', {}).get('award_guaranteed') is not False
                    or receipt.get('release', {}).get('application_submitted') is not False
                    or receipt.get('release', {}).get('externally_sent') is not False
                    or len(shortlist) != 1
                    or shortlist[0].get('opportunity_id') != 'SERVICES-SETA-DG-2026-27-03'
                    or shortlist[0].get('fit_state') != 'unknown_review_required'
                    or shortlist[0].get('timing_state') != 'within_stated_deadline'
                    or shortlist[0].get('deadline') != '2026-11-15'
                    or shortlist[0].get('official_url') != 'https://serviceseta.org.za/discretionary-grant-funding-window-2026-27-now-open/'
                    or len(shortlist[0].get('criteria') or []) != 6
                    or any(row.get('state') != 'unknown' for row in shortlist[0].get('criteria') or [])
                    or len(shortlist[0].get('required_documents') or []) != 5
                    or evidence.get('required_document_count') != 5
                    or evidence.get('supporting_source_count') != 4
                    or evidence.get('application_system_status_quote_bound') is not True
                    or not any(row.get('name') == 'application system for this window is currently unavailable' and row.get('source_supported') is True for row in shortlist[0].get('required_documents') or [])
                    or not any(row.get('source_id') == 'DG03-UPDATE' and row.get('url') == 'https://serviceseta.org.za/update-on-the-2026-27-funding-windows/' for row in evidence.get('supporting_sources') or [])
                    or evidence.get('criterion_states') != {row.get('criterion_id'): 'unknown' for row in shortlist[0].get('criteria') or []}
                    or not source_sha or source_sha != shortlist[0].get('source_sha256')
                    or evidence.get('official_source', {}).get('sha256') != source_sha
                    or evidence.get('eligibility_certified') is not False
                    or evidence.get('application_submitted') is not False
                    or evidence.get('release_authorized') is not False):
                raise ValueError('FundingFinder Services SETA current-source route failed its source/hash or held-output contract')
            product_specific_refs.extend([register(evidence_path), register(FUNDING_FINDER_SERVICESETA_PACKET), register(execution_path), register(ROOT / 'scripts/run_fundingfinder_services_seta_candidate_v9.py')])
            for artifact_row in execution.get('artifacts') or []:
                product_specific_refs.append(register(FUNDING_FINDER_SERVICESETA_ROUTE / artifact_row['path'], artifact_row.get('sha256')))
            changes.append('FundingFinder refreshed the official DG-03 window page and supporting documents on 4 November, captured the current system-unavailable notice, and bound the extended 15 November 2026 deadline to the exact captured quotation. The route keeps all six synthetic applicant checks unresolved and records that submission is currently unavailable; eligibility certification and application submission remain disabled.')
            limits.append('The synthetic profile does not establish eligible applicant role, qualifying learning programme, Annexure A priority alignment, programme count, unemployed learner age composition or submission readiness. The official page says applications cannot currently be submitted; monitor Services SETA for application arrangements and confirm current requirements. This route does not certify eligibility or award likelihood.')
        if name == 'FundingFinder' and FUNDING_FINDER_THREE_WINDOW_DATA.is_file():
            window_map = read_json(FUNDING_FINDER_THREE_WINDOW_DATA)
            window_receipt = read_json(FUNDING_FINDER_THREE_WINDOW_RECEIPT)
            if (window_map.get('schema') != 'dio.fundingfinder.serviceseta.three_window_review.v1'
                    or window_map.get('as_of_date') != '2026-11-04'
                    or len(window_map.get('pages') or []) != 5
                    or len(window_map.get('documents') or []) != 10
                    or len(window_map.get('windows') or []) != 3
                    or any(row.get('closing_date') != '2026-11-15' or row.get('application_system_state') != 'CURRENTLY_UNAVAILABLE' for row in window_map.get('windows') or [])
                    or window_map.get('withdrawal_controls', {}).get('prior_applications_transfer_automatically') is not False
                    or window_map.get('withdrawal_controls', {}).get('new_application_required') is not True
                    or window_map.get('product_boundaries', {}).get('eligibility_certified') is not False
                    or window_map.get('product_boundaries', {}).get('technical_scoring_enabled_for_SP04_or_SP01') is not False
                    or window_map.get('product_boundaries', {}).get('application_submitted') is not False
                    or window_receipt.get('schema') != 'dio.fundingfinder.serviceseta.three_window_review_receipt.v1'
                    or window_receipt.get('window_count') != 3
                    or window_receipt.get('withdrawal_controls_verified') is not True
                    or any(window_map.get('evaluation_criteria_observations', {}).get(window, {}).get('state') != 'CONFLICT_REQUIRES_FUNDER_CONFIRMATION'
                           for window in ('SP04', 'SP01'))):
                raise ValueError('FundingFinder Services SETA three-window package does not preserve current source coverage and held eligibility/scoring boundaries')
            source_paths = []
            for source in window_map['pages']:
                raw_path = FUNDING_FINDER_THREE_WINDOW_RUN / source['captured_path']
                text_path = FUNDING_FINDER_THREE_WINDOW_RUN / source['extracted_text_path']
                if (not raw_path.is_file() or not text_path.is_file()
                        or hashlib.sha256(raw_path.read_bytes()).hexdigest() != source.get('sha256')
                        or hashlib.sha256(text_path.read_bytes()).hexdigest() != source.get('extracted_text_sha256')):
                    raise ValueError(f"FundingFinder official page source hash mismatch: {source.get('id')}")
                page_text = text_path.read_text(encoding='utf-8')
                if any(quote not in page_text for quote in source.get('quotes') or []):
                    raise ValueError(f"FundingFinder page fact quote is not present in its captured text: {source.get('id')}")
                source_paths.extend([(raw_path, source['sha256']), (text_path, source['extracted_text_sha256'])])
            for source in window_map['documents']:
                raw_path = FUNDING_FINDER_THREE_WINDOW_RUN / source['captured_path']
                if not raw_path.is_file() or hashlib.sha256(raw_path.read_bytes()).hexdigest() != source.get('sha256'):
                    raise ValueError(f"FundingFinder official document hash mismatch: {source.get('id')}")
                source_paths.append((raw_path, source['sha256']))
                text_info = source.get('extracted_text') or {}
                if text_info.get('path'):
                    text_path = FUNDING_FINDER_THREE_WINDOW_RUN / text_info['path']
                    if (not text_path.is_file() or hashlib.sha256(text_path.read_bytes()).hexdigest() != text_info.get('sha256')
                            or text_info.get('has_text') is not True):
                        raise ValueError(f"FundingFinder official document text hash mismatch: {source.get('id')}")
                    source_paths.append((text_path, text_info['sha256']))
            for output in window_receipt.get('outputs') or []:
                path = ROOT / output['path']
                if not path.is_file() or hashlib.sha256(path.read_bytes()).hexdigest() != output.get('sha256'):
                    raise ValueError(f"FundingFinder window review output hash mismatch: {output.get('path')}")
                product_specific_refs.append(register(path, output['sha256']))
            product_specific_refs.extend([register(FUNDING_FINDER_THREE_WINDOW_RECEIPT),
                                          register(ROOT / 'scripts/build_fundingfinder_serviceseta_window_map_v4.py')])
            for path, digest in source_paths:
                product_specific_refs.append(register(path, digest))
            changes.append('FundingFinder maps DG-03, SP-04 and SP-01 against a 4 November capture of all three official window pages plus the 3 November update notice and ten linked documents. All three show the extended 15 November 2026 deadline and current system unavailability; withdrawn DG-02/SP-03 remain flagged. Pending-approval language and SP-03 labels in the SP-04/SP-01 evaluation PDFs continue to block technical scoring.')
            limits.append('The application system is currently unavailable and Services SETA has not published application arrangements in the captured notice. Applicant eligibility, required records, final approved strategic criteria and closing time remain unverified; no eligibility decision, score, award likelihood or submission is asserted.')
        if name in {'HOMS Assess', 'HOMS Exam', 'HOMS Exam Studio'}:
            limits.append('Assessment reasoning quality remains an unresolved qualification gap.')
        if name == 'HOMS Assess':
            product_specific_refs.extend([register(ROOT / 'scripts/run_homs_hymark_batch.py'),
                                           register(ROOT / 'products/homs_assess_customer.py')])
            changes.append('The current assessor implementation keeps every automated total and percentage in proposal fields only; issued score and gradebook fields remain blank until educator adjudication, even when automated checks detect no contradiction.')
            score_gate = OUTPUT / 'HOMS_ASSESS_SCORE_FIELD_GATE_EXECUTION_20261101_V1'
            score_package = read_json(score_gate / 'CUSTOMER_PACKAGE_RECEIPT.json')
            score_results = read_json(score_gate / score_package['outputs']['results'])
            score_csv = score_gate / score_package['outputs']['marks_csv']
            with score_csv.open('r', encoding='utf-8', newline='') as handle:
                score_rows = list(csv.DictReader(handle))
            if (score_package.get('withheld_score_count') != len(score_results)
                    or any(row.get('total_score') is not None or row.get('percentage') is not None or row.get('score_issued') is not False for row in score_results)
                    or any(row.get('score') or row.get('percentage') for row in score_rows)):
                raise ValueError('HOMS Assess score-field gate execution issued an automated score')
            changes.append('A fresh local Grade 10 route returned blank total and percentage fields in learner results and score columns in the marks CSV; both synthetic learners remained blocked with incomplete pointwise responses.')
            limits.append('The fresh route confirms blank fields for blocked/incomplete submissions. It does not exercise a clean, unflagged proposal, and it provides no scoring-accuracy, educator-acceptance or classroom-release evidence.')
        if name == 'HOMS Assess':
            adjudication_validator = ROOT / 'products/homs_assess_customer.py'
            product_specific_refs.append(register(adjudication_validator))
            changes.append('Pointwise educator adjudication now rejects review timestamps that are not timezone-aware ISO-8601 values, for both individual marks and marking-quality flag decisions; empty fields still remain unresolved and no marks are issued.')
        if name == 'HOMS Assess' and HOMS_ASSESS_QUALITY_REPORT.is_file():
            changes.append('Current feedback/source consistency gate catches missing-direction claims and requests for unit clarification when exact learner quotes already contain those features. Replaced feedback still asks educators to verify unit completeness and dimensions; scores remain provisional.')
            register(HOMS_ASSESS_QUALITY_REPORT)
        if name == 'HOMS Assess' and HOMS_ASSESS_CUSTOMER_DEMO.is_dir():
            package_path = HOMS_ASSESS_CUSTOMER_DEMO / 'CUSTOMER_PACKAGE_RECEIPT.json'
            execution_path = HOMS_ASSESS_CUSTOMER_DEMO / 'CUSTOMER_EXECUTION_RECEIPT.json'
            if execution_path.is_file():
                execution_receipt = read_json(execution_path)
                for artifact_row in execution_receipt.get('artifacts', []):
                    path = HOMS_ASSESS_CUSTOMER_DEMO / artifact_row['path']
                    if path.is_file(): register(path, artifact_row.get('sha256'))
            if package_path.is_file():
                packet_receipt = read_json(package_path)
                if packet_receipt.get('score_withholding_invariants_passed') is not True or packet_receipt.get('external_processing') is not False:
                    raise ValueError('HOMS Assess customer execution failed local-only/score-withholding boundary checks')
                if packet_receipt.get('withheld_score_count') != packet_receipt.get('submission_count'):
                    raise ValueError('HOMS Assess feedback/score gate evidence did not withhold every synthetic proposal')
                changes.append('A fresh Grade 10 customer route now keeps feedback wording repair separate from score adjudication: the exact-quote unit inconsistency and graph-concept conflict stay unresolved scoring flags. The local assessor also omitted memo point 1.3.P10 for both learners, so both totals were withheld, zero points were silently defaulted, and classroom release stayed false.')
                limits.append('The local Granite 3.2 2B response was incomplete for both synthetic learners; this run proves safe score withholding under the observed failure, not marking accuracy or reliable assessment completion.')
                for relative in packet_receipt.get('outputs', {}).values():
                    if relative:
                        path = HOMS_ASSESS_CUSTOMER_DEMO / relative
                        if path.is_file(): register(path)
                product_specific_refs.append(register(package_path))
            for path in (execution_path,
                         HOMS_ASSESS_CUSTOMER_DEMO / 'CUSTOMER_ASSESS_REVIEW.html',
                         HOMS_ASSESS_CUSTOMER_DEMO / 'projection/ENGINE_INPUT.json',
                         HOMS_ASSESS_CUSTOMER_DEMO / 'input/ASSESSMENT_BINDING_RECEIPT.json'):
                if path.is_file(): product_specific_refs.append(register(path))
            disposition = 'CURRENT_HELD_EXECUTION_VERIFIED'
            changes.append('The latest local-only Grade 10 route performs two independent pointwise scoring passes per learner over 50 source-bound memo points. V17 matched each learner’s paired pass; it withheld learner B’s numeric score for a motion-graph concept conflict and kept learner A’s 42/50 proposal provisional for educator review.')
            pointwise_batch = ROOT / 'acceptance_runs/68-product-sellability-20261027/HOMS_ASSESS_CUSTOMER_PACKET_EXECUTION_20261101_G10_V13/hymark/homs-hymark-input-20261101T152320Z/HOMS_HYMARK_BATCH_RECEIPT.json'
            pointwise_results = pointwise_batch.with_name('results.json')
            if pointwise_batch.is_file() and pointwise_results.is_file():
                batch = read_json(pointwise_batch)
                results = read_json(pointwise_results)
                if batch.get('score_issuance') != 'BLOCKED_MARKING_QUALITY_FLAGS' or batch.get('provider_errors') is None or len(results) != 2 or any(item.get('total_score') is not None for item in results):
                    raise ValueError('HOMS Assess V13 pointwise follow-up must retain two blocked, unissued learner results')
                product_specific_refs.extend([register(pointwise_batch), register(pointwise_results)])
                changes.append('A follow-up preserved the source memo’s 50 point allocations across five criteria and asked for point-level marks with learner quotes. V13 returned incomplete/ungrounded pointwise responses for both learners; issuance remained blocked and no numeric score was released.')
                limits.append('The local 2.5B scorer did not satisfy the pointwise response contract in V13, after about 572 seconds. This is a provider completeness/throughput failure, not evidence that the pointwise mark proposals are accurate.')
        if name == 'HOMS Assess' and HOMS_ASSESS_REASONING_REPEATABILITY.is_file():
            reasoning = read_json(HOMS_ASSESS_REASONING_REPEATABILITY)
            observations = reasoning.get('observations') or {}
            if observations.get('latest_independent_passes_match') is not True or observations.get('latest_scores_provisional_only') is not True or observations.get('classroom_release_authorized') is not False or observations.get('latest_numeric_proposals_withheld') is not True or observations.get('latest_withheld_score_count') != 1 or observations.get('latest_run') != 'V17':
                raise ValueError('HOMS Assess latest reasoning evidence must show V17 paired passes and one withheld numeric proposal')
            product_specific_refs.append(register(HOMS_ASSESS_REASONING_REPEATABILITY))
            for comparison in reasoning.get('comparison_runs') or []:
                for path_key, digest_key in (('results_path', 'results_sha256'), ('batch_receipt_path', 'batch_receipt_sha256')):
                    relative = comparison.get(path_key)
                    if relative:
                        product_specific_refs.append(register(ROOT / relative, comparison.get(digest_key)))
            changes.append('The exact-quote guard catches direction and unit feedback conflicts; V17 also restores the motion-graph conflict gate from the source question and pointwise memo. Both learners matched their independent paired passes; learner B’s graph-concept conflict withheld that proposal.')
            limits.append('Matched paired passes do not prove scoring correctness or cross-run stability. Learner A’s 42/50 remains provisional and learner B’s score is withheld; an educator must confirm every mark and feedback line against the memo.')
        if name == 'HOMS Assess' and HOMS_ASSESS_GRAPH_CONFLICT_EVIDENCE.is_file():
            evidence = read_json(HOMS_ASSESS_GRAPH_CONFLICT_EVIDENCE)
            execution_path = HOMS_ASSESS_SOURCE_GROUNDED_DEMO / 'CUSTOMER_EXECUTION_RECEIPT.json'
            package_path = HOMS_ASSESS_SOURCE_GROUNDED_DEMO / 'CUSTOMER_PACKAGE_RECEIPT.json'
            package = read_json(package_path)
            results_path = HOMS_ASSESS_SOURCE_GROUNDED_DEMO / package['outputs']['results']
            results = read_json(results_path)
            learner_b = next((row for row in results if row.get('student_id') == 'learner_B'), {})
            graph_flags = [flag for flag in learner_b.get('unresolved_marking_quality_flags') or []
                           if flag.get('code') == 'learner_quote_conflicts_with_motion_graph_rubric'
                           and flag.get('criterion') == '1.5']
            if (package.get('source_packet_manifest_sha256') != evidence.get('source_packet_manifest_sha256')
                    or digest_file(execution_path) != evidence.get('execution_receipt_sha256')
                    or digest_file(package_path) != evidence.get('package_receipt_sha256')
                    or digest_file(results_path) != evidence.get('results_sha256')
                    or package.get('withheld_score_count') != 2
                    or package.get('provisional_score_count') != 0
                    or package.get('classroom_release_authorized') is not False
                    or len(graph_flags) != 1
                    or graph_flags[0].get('source_quote') != evidence.get('checks', {}).get('learner_b_exact_source_quote')
                    or learner_b.get('criteria_scores', {}).get('1.5', {}).get('score') != 12.0):
                raise ValueError('HOMS Assess source-grounded graph-conflict evidence is stale or its held-score assertions changed')
            for path in (HOMS_ASSESS_GRAPH_CONFLICT_EVIDENCE, execution_path, package_path, results_path):
                product_specific_refs.append(register(path))
            changes.append('The latest source-bound Grade 10 HOMS Assess run uses the refreshed exam/memo/rubric and now detects a graph misconception directly in the learner submission, preserving the exact contradictory sentence in the educator flag.')
            limits.append('In V28, the local model still proposed 12/12 on the contradicted graph criterion and left one separate memo point unreturned per learner. Both assessment totals were withheld; the graph proposal remains unaccepted and requires direct educator adjudication. Scoring accuracy and product qualification remain unproved.')
        if name == 'HOMS Assess' and HOMS_ASSESS_QUESTION_SCOPED_CONFLICT_REPLAY.is_file():
            replay = read_json(HOMS_ASSESS_QUESTION_SCOPED_CONFLICT_REPLAY)
            replay_flags = [flag for learner in replay.get('learner_results') or [] for flag in learner.get('flags') or []]
            replay_keys = {(flag.get('question_id'), flag.get('code')) for flag in replay_flags}
            if (replay.get('schema') != 'dio.homs.assess.question_scoped_conflict_replay.v1'
                    or replay.get('state') != 'PASS_QUESTION_SCOPED_SOURCE_REPLAY'
                    or replay.get('learner_count') != 2
                    or replay.get('question_scoped_source_binding_pass') is not True
                    or replay.get('marking_accuracy_established') is not False
                    or replay.get('scores_issued') is not False
                    or replay.get('classroom_release_authorized') is not False
                    or ('1.5', 'learner_quote_conflicts_with_motion_graph_rubric') not in replay_keys
                    or any(not flag.get('source_quote_parts_bound_to_question_answer') or flag.get('resolution_eligible') is not False for flag in replay_flags)):
                raise ValueError('HOMS Assess question-scoped conflict replay lost answer-source binding or its held boundary')
            product_specific_refs.extend([
                register(HOMS_ASSESS_QUESTION_SCOPED_CONFLICT_REPLAY),
                register(ROOT / 'scripts/run_homs_assess_question_scoped_conflict_replay.py'),
                register(ROOT / 'scripts/run_homs_hymark_batch.py'),
            ])
            changes.append('The deterministic distance/definition and motion-graph conflict guards now inspect only the matching numbered learner answer. A retrospective source-bound replay surfaced learner B’s distance discrepancy in Q1.1 and both graph-relationship conflicts in Q1.5; each exact quote remains a non-resolvable educator flag, with no scores issued.')
            limits.append('The question-scoped replay uses two synthetic Grade 10 submissions and does not establish marking accuracy, general language coverage, provider reliability, or classroom readiness. Educator adjudication remains required.')
        if name == 'HOMS Assess' and HOMS_ASSESS_FRESH_GUARD_RUN.is_dir():
            execution_path = HOMS_ASSESS_FRESH_GUARD_RUN / 'CUSTOMER_EXECUTION_RECEIPT.json'
            package_path = HOMS_ASSESS_FRESH_GUARD_RUN / 'CUSTOMER_PACKAGE_RECEIPT.json'
            execution, package = map(read_json, (execution_path, package_path))
            results_path = HOMS_ASSESS_FRESH_GUARD_RUN / package['outputs']['results']
            results = read_json(results_path)
            learner_b = next((row for row in results if row.get('student_id') == 'learner_B'), {})
            graph_flags = [flag for flag in learner_b.get('unresolved_marking_quality_flags') or []
                           if flag.get('code') == 'learner_quote_conflicts_with_motion_graph_rubric'
                           and flag.get('criterion') == '1.5']
            if (execution.get('external_effects') is not False
                    or package.get('source_packet_manifest_sha256') != 'ebbb1925e41c6dc4c5c7e8fba87885013d06843408ec3a6ff8a512686edb8d7e'
                    or package.get('withheld_score_count') != 2
                    or package.get('provisional_score_count') != 0
                    or package.get('classroom_release_authorized') is not False
                    or len(results) != 2
                    or any(row.get('total_score') is not None for row in results)
                    or len(graph_flags) != 1):
                raise ValueError('HOMS Assess fresh safeguard route did not preserve source binding, graph conflict, or held scores')
            for path in (execution_path, package_path, results_path,
                         HOMS_ASSESS_FRESH_GUARD_RUN / package['outputs']['marks_csv'],
                         ROOT / 'scripts/run_homs_hymark_batch.py'):
                product_specific_refs.append(register(path))
            changes.append('A fresh source-bound Grade 10 run under the updated HOMS Assess safeguard completed through the customer route. The source motion-graph conflict remained flagged; both learner totals were withheld after incomplete pointwise proposals, with classroom release and external effects disabled. The definition-swap detector was broadened in source, but this fixture did not exercise that specific branch.')
            limits.append('An earlier fresh route did not exercise the targeted definition reversal. The later V3 route exercises one exact wording only; broader concept detection, scoring accuracy and educator acceptance remain unproved, and provider incompleteness persists.')
        if name == 'HOMS Assess' and HOMS_ASSESS_INTERACTIVE_EDUCATOR_RUN.is_dir():
            run_dir = HOMS_ASSESS_INTERACTIVE_EDUCATOR_RUN
            execution_path = run_dir / 'CUSTOMER_EXECUTION_RECEIPT.json'
            package_path = run_dir / 'CUSTOMER_PACKAGE_RECEIPT.json'
            execution, package = map(read_json, (execution_path, package_path))
            outputs = package.get('outputs') or {}
            review_path = run_dir / outputs.get('pointwise_educator_review', '')
            review_receipt_path = run_dir / outputs.get('pointwise_review_receipt', '')
            adjudication_path = run_dir / outputs.get('pointwise_adjudication_csv', '')
            adjudication_receipt_path = run_dir / outputs.get('pointwise_adjudication_receipt', '')
            quality_path = run_dir / outputs.get('quality_flag_review_csv', '')
            guide_path = run_dir / outputs.get('pointwise_adjudication_guide', '')
            workspace_upgrade_ref = package.get('educator_review_workspace_upgrade_receipt') or {}
            workspace_upgrade_path = run_dir / str(workspace_upgrade_ref.get('path') or '')
            review_receipt, adjudication_receipt = map(read_json, (review_receipt_path, adjudication_receipt_path))
            workspace_upgrade = read_json(workspace_upgrade_path)
            artifact_hashes = {row['path']: row['sha256'] for row in execution.get('artifacts') or []}
            for path in (review_path, review_receipt_path, adjudication_path,
                         adjudication_receipt_path, quality_path, guide_path):
                relative = path.relative_to(run_dir).as_posix()
                if not path.is_file() or artifact_hashes.get(relative) != digest_file(path):
                    raise ValueError(f'HOMS Assess interactive educator artifact hash mismatch: {relative}')
            page_text = review_path.read_text(encoding='utf-8')
            with adjudication_path.open('r', encoding='utf-8-sig', newline='') as handle:
                point_reader = csv.DictReader(handle)
                point_rows = list(point_reader)
                point_fields = set(point_reader.fieldnames or [])
            with quality_path.open('r', encoding='utf-8-sig', newline='') as handle:
                flag_reader = csv.DictReader(handle)
                flag_rows = list(flag_reader)
                flag_fields = set(flag_reader.fieldnames or [])
            educator_fields = ('educator_verified_marks', 'educator_decision', 'educator_rationale',
                               'educator_reviewer', 'reviewed_at', 'educator_verified_source_quote')
            flag_decision_fields = ('educator_resolution', 'educator_rationale', 'educator_reviewer', 'reviewed_at')
            if (package.get('local_provider', {}).get('selected_model') != 'granite3.3:2b'
                    or package.get('submission_count') != 2
                    or package.get('pointwise_marking_point_count') != 50
                    or len(point_rows) != 100 or len(flag_rows) != 33
                    or not set(educator_fields).issubset(point_fields)
                    or not set(flag_decision_fields).issubset(flag_fields)
                    or any(any(row.get(field) for field in educator_fields) for row in point_rows)
                    or any(any(row.get(field) for field in flag_decision_fields) for row in flag_rows)
                    or page_text.count("data-point-row='") != 100
                    or page_text.count("data-flag-row='") != 33
                    or 'Download educator review CSVs' not in page_text
                    or 'Save review draft JSON' not in page_text
                    or 'Resume from draft JSON' not in page_text
                    or 'filter-unresolved' not in page_text
                    or 'localStorage' in page_text
                    or 'fetch(' in page_text
                    or 'URL.createObjectURL' not in page_text
                    or review_receipt.get('page_sha256') != digest_file(review_path)
                    or review_receipt.get('draft_resume_supported') is not True
                    or review_receipt.get('draft_contains_educator_fields_only') is not True
                    or not review_receipt.get('draft_context_sha256')
                    or review_receipt.get('draft_context_binds_source_and_model_proposals') is not True
                    or review_receipt.get('browser_storage_used') is not False
                    or review_receipt.get('network_requests_from_review_surface') is not False
                    or workspace_upgrade_ref.get('sha256') != digest_file(workspace_upgrade_path)
                    or workspace_upgrade.get('schema') != 'dio.homs.assess.educator_review_workspace_upgrade.v1'
                    or workspace_upgrade.get('customer_packet_fingerprint') != package.get('customer_packet_fingerprint')
                    or workspace_upgrade.get('point_row_count') != 100
                    or workspace_upgrade.get('quality_flag_row_count') != 33
                    or workspace_upgrade.get('scores_issued') is not False
                    or workspace_upgrade.get('classroom_release_authorized') is not False
                    or workspace_upgrade.get('external_processing') is not False
                    or (workspace_upgrade.get('features') or {}).get('save_draft_json') is not True
                    or (workspace_upgrade.get('features') or {}).get('resume_draft_json') is not True
                    or (workspace_upgrade.get('features') or {}).get('draft_contains_educator_fields_only') is not True
                    or (workspace_upgrade.get('features') or {}).get('draft_context_binds_source_and_model_proposals') is not True
                    or (workspace_upgrade.get('features') or {}).get('browser_storage_used') is not False
                    or (workspace_upgrade.get('features') or {}).get('network_requests_from_review_surface') is not False
                    or any(digest_file(run_dir / relative) != expected
                           for relative, expected in (workspace_upgrade.get('changed_artifact_sha256') or {}).items())
                    or adjudication_receipt.get('point_row_count') != 100
                    or adjudication_receipt.get('source_quality_flag_row_count') != 33
                    or adjudication_receipt.get('assessment_total_issued') is not False
                    or adjudication_receipt.get('classroom_release_authorized') is not False
                    or package.get('withheld_score_count') != 2
                    or package.get('provisional_score_count') != 0
                    or package.get('classroom_release_authorized') is not False
                    or package.get('external_processing') is not False):
                raise ValueError('HOMS Assess interactive educator handoff is incomplete or changed its score-release boundary')
            product_specific_refs.extend([
                register(execution_path), register(package_path), register(review_path, artifact_hashes[review_path.relative_to(run_dir).as_posix()]),
                register(review_receipt_path, artifact_hashes[review_receipt_path.relative_to(run_dir).as_posix()]),
                register(adjudication_path, artifact_hashes[adjudication_path.relative_to(run_dir).as_posix()]),
                register(adjudication_receipt_path, artifact_hashes[adjudication_receipt_path.relative_to(run_dir).as_posix()]),
                register(quality_path, artifact_hashes[quality_path.relative_to(run_dir).as_posix()]),
                register(guide_path, artifact_hashes[guide_path.relative_to(run_dir).as_posix()]),
                register(workspace_upgrade_path, workspace_upgrade_ref.get('sha256')),
            ])
            changes.append('The Granite 3.3 Grade 10 route now has a refreshed browser handoff with learner/text filters, unresolved-only view and a packet-bound JSON draft save/resume flow. Drafts store educator decisions only and are downloaded locally; the surface does not use browser storage or network requests. The handoff covers 100 memo-point rows and 33 marking-quality flags; both learner totals remain withheld.')
            limits.append('The interactive form only prepares educator CSVs. The existing validator must check each entry; no score is issued, no classroom release is authorized, and the synthetic route does not establish scoring accuracy or educator acceptance.')
        if name == 'HOMS Assess' and HOMS_ASSESS_GROUNDED_ADJUDICATION_RUN.is_dir():
            repair_path = HOMS_ASSESS_PACKET_PATH_REPAIR
            repair = read_json(repair_path)
            repaired_packet = HOMS_ASSESS_GROUNDED_ADJUDICATION_RUN.parent / 'HOMS_ASSESS_SOURCE_PACKET_REPAIRED_20261102' / 'CUSTOMER_PACKET'
            manifest_path = repaired_packet / 'CUSTOMER_PACKET_MANIFEST.json'
            binding_path = repaired_packet / 'SOURCES/hymark_input/assessment_binding.json'
            package_path = HOMS_ASSESS_GROUNDED_ADJUDICATION_RUN / 'CUSTOMER_PACKAGE_RECEIPT.json'
            execution_path = HOMS_ASSESS_GROUNDED_ADJUDICATION_RUN / 'CUSTOMER_EXECUTION_RECEIPT.json'
            package, execution = map(read_json, (package_path, execution_path))
            csv_path = HOMS_ASSESS_GROUNDED_ADJUDICATION_RUN / package['outputs']['pointwise_adjudication_csv']
            adjudication_receipt_path = HOMS_ASSESS_GROUNDED_ADJUDICATION_RUN / package['outputs']['pointwise_adjudication_receipt']
            review_receipt_path = HOMS_ASSESS_GROUNDED_ADJUDICATION_RUN / package['outputs']['pointwise_review_receipt']
            with csv_path.open('r', encoding='utf-8-sig', newline='') as handle:
                csv_reader = csv.DictReader(handle)
                assessment_adjudication_rows = list(csv_reader)
                assessment_csv_fields = set(csv_reader.fieldnames or [])
            if (repair.get('schema') != 'dio.homs.assess.customer_packet_path_repair.v1'
                    or repair.get('all_bound_sources_exist_and_hash_match') is not True
                    or repair.get('examiner_material_included') is not False
                    or repair.get('release_authorized') is not False
                    or package.get('product_name') != 'HOMS Assess'
                    or package.get('source_packet_manifest_sha256') != digest_file(manifest_path)
                    or package.get('assessment_binding_sha256') != digest_file(HOMS_ASSESS_GROUNDED_ADJUDICATION_RUN / 'input/ASSESSMENT_BINDING_RECEIPT.json')
                    or package.get('submission_count') != 2
                    or package.get('withheld_score_count') != 2
                    or package.get('provisional_score_count') != 0
                    or package.get('classroom_release_authorized') is not False
                    or execution.get('release_authorized') is not False
                    or execution.get('external_effects') is not False
                    or len(assessment_adjudication_rows) != 100
                    or 'educator_verified_source_quote' not in assessment_csv_fields
                    or any(row.get('educator_verified_source_quote') for row in assessment_adjudication_rows)
                    or digest_file(csv_path) != package.get('pointwise_adjudication_sha256')
                    or digest_file(review_receipt_path) != package.get('pointwise_review_receipt_sha256')
                    or digest_file(adjudication_receipt_path) != package.get('pointwise_adjudication_receipt_sha256')):
                raise ValueError('HOMS Assess refreshed customer handoff lacks packet lineage, quote gate, or withheld-score boundary')
            product_specific_refs.extend([register(repair_path), register(manifest_path), register(binding_path),
                                          register(package_path), register(execution_path), register(csv_path),
                                          register(review_receipt_path), register(adjudication_receipt_path),
                                          register(HOMS_ASSESS_GROUNDED_ADJUDICATION_RUN / package['outputs']['pointwise_educator_review']),
                                          register(HOMS_ASSESS_GROUNDED_ADJUDICATION_RUN / package['outputs']['pointwise_adjudication_guide'])])
            changes.append('A repaired synthetic customer packet now resolves all nine assessment source artifacts from the packet root and verifies each path/hash against its manifest. A fresh Grade 10 route rendered the updated 100-row pointwise handoff with the new exact educator-quote field; both learners’ automated totals stayed withheld because the local scorer returned incomplete or ungrounded proposals.')
            limits.append('The new route verifies customer packet binding and review-surface delivery, not marking accuracy. The local provider failed its bounded completeness/grounding gate for both learners; no score was issued, and educator review remains required.')
        if name == 'HOMS Assess' and HOMS_ASSESS_GRANITE33_COMPARISON_RUN.is_dir():
            comparison_path = HOMS_ASSESS_GRANITE33_COMPARISON_RUN / 'GRANITE33_CURRENT_ROUTE_COMPARISON_EVIDENCE.json'
            comparison = read_json(comparison_path)
            comparison_current = comparison.get('current_run') or {}
            comparison_baseline = comparison.get('baseline_run') or {}
            if (comparison.get('schema') != 'dio.homs.assess.granite_model_comparison.v1'
                    or comparison.get('same_source_packet') is not True
                    or comparison_current.get('model') != 'granite3.3:2b'
                    or comparison_baseline.get('model') != 'granite3.2:2b'
                    or comparison_current.get('expected_point_count') != 100
                    or comparison_baseline.get('expected_point_count') != 100
                    or comparison_current.get('missing_point_id_count') != 0
                    or comparison_baseline.get('missing_point_id_count') != 0
                    or comparison_current.get('positive_proposals_with_exact_source_quote_count') != 56
                    or comparison_baseline.get('positive_proposals_with_exact_source_quote_count') != 0
                    or comparison_current.get('positive_proposals_without_exact_source_quote_count') != 28
                    or comparison_current.get('all_totals_blank') is not True
                    or comparison_baseline.get('all_totals_blank') is not True
                    or comparison.get('all_totals_withheld') is not True
                    or comparison.get('classroom_release_authorized') is not False):
                raise ValueError('HOMS Assess Granite model comparison is stale, mismatched, or crosses the held-score boundary')
            product_specific_refs.append(register(comparison_path))
            package_path = HOMS_ASSESS_GRANITE33_COMPARISON_RUN / 'CUSTOMER_PACKAGE_RECEIPT.json'
            package = read_json(package_path)
            result_path = HOMS_ASSESS_GRANITE33_COMPARISON_RUN / package['outputs']['results']
            for subpath in (HOMS_ASSESS_GRANITE33_COMPARISON_RUN / 'CUSTOMER_EXECUTION_RECEIPT.json',
                            package_path, result_path,
                            ROOT / 'scripts/run_homs_assess_granite33_comparison_v30.py', ROOT / 'products/homs_assess_customer.py'):
                if subpath.is_file():
                    product_specific_refs.append(register(subpath))
            changes.append('A same-packet controlled comparison justified changing HOMS Assess’s default local model to Granite 3.3: it returned all 100/100 point IDs and exact source quotes for 56/84 positive proposals, compared with 0/98 exact positive quotes from Granite 3.2. The default-model route continues to hold totals for educator review. The comparison keeps both learner totals blank and shows the current Granite 3.3 route still has 28 positive proposals without exact quotes.')
            limits.append('The controlled synthetic comparison improves response completeness and exact-quote coverage only. Both runs remain blocked with blank totals; no scoring-accuracy evidence, educator acceptance or classroom release is established.')
        if name == 'HOMS Assess' and HOMS_ASSESS_QWEN3_NOTHINK_RUN.is_dir():
            probe_path = HOMS_ASSESS_QWEN3_NOTHINK_RUN / 'QWEN3_NOTHINK_PROBE_STATUS.json'
            if probe_path.is_file():
                probe = read_json(probe_path)
                if (probe.get('schema') != 'dio.homs.assess.qwen3_nothink_probe_status.v1'
                        or probe.get('state') != 'INCOMPLETE_ABORTED_FOR_EXCESSIVE_LATENCY'
                        or probe.get('model') != 'qwen3:4b'
                        or probe.get('elapsed_seconds_at_stop', 0) < 480
                        or probe.get('completed_learner_results') != 0
                        or probe.get('totals_issued') is not False
                        or probe.get('classroom_release_authorized') is not False):
                    raise ValueError('HOMS Assess Qwen3 non-thinking probe status is incomplete or misclassified')
                for partial_row in probe.get('partial_artifacts') or []:
                    path = ROOT / partial_row.get('path', '')
                    if not path.is_file() or digest_file(path) != partial_row.get('sha256'):
                        raise ValueError('HOMS Assess Qwen3 non-thinking partial artifact hash mismatch')
                product_specific_refs.extend([
                    register(probe_path),
                    register(ROOT / 'scripts/run_homs_assess_qwen3_nothink_probe.py'),
                    register(ROOT / 'scripts/run_homs_hymark_batch.py'),
                    register(ROOT / 'products/homs_assess_customer.py'),
                ])
                changes.append('A controlled Qwen3 4B non-thinking-mode probe did not return a first learner result within 509 seconds on the local CPU-backed Ollama runner. The partial run is retained as explicitly incomplete evidence and is not used for model selection.')
                limits.append('Qwen3 remains unqualified for HOMS Assess in this environment because even the non-thinking prompt-mode probe exceeded practical latency. Granite 3.3 remains the local default, with totals held pending educator review.')
        if name == 'HOMS Assess' and HOMS_ASSESS_CLEAN_RUN_REPEATABILITY.is_file():
            clean_evidence = read_json(HOMS_ASSESS_CLEAN_RUN_REPEATABILITY)
            clean_runs = {item.get('label'): item for item in clean_evidence.get('runs') or []}
            clean_checks = clean_evidence.get('checks') or {}
            clean_run = clean_runs.get('granite33_clean_run') or {}
            run_1 = clean_runs.get('granite33_run_1') or {}
            run_2 = clean_runs.get('granite33_run_2') or {}
            if (clean_evidence.get('schema') != 'dio.homs.assess.clean_run_and_model_repeatability_evidence.v1'
                    or not all(clean_checks.get(key) is True for key in (
                        'same_six_source_input_hashes', 'candidate_model_and_temperature_recorded',
                        'clean_run_removed_inherited_score_outputs', 'candidate_total_scores_all_withheld',
                        'granite33_run_1_and_run_2_differ', 'granite33_run_2_matches_clean_run'))
                    or len(clean_evidence.get('input_file_sha256') or {}) != 6
                    or clean_evidence.get('score_issuance') != 'BLOCKED_FOR_EDUCATOR_REVIEW'
                    or clean_evidence.get('classroom_release_authorized') is not False
                    or run_1.get('results_sha256') == run_2.get('results_sha256')
                    or run_2.get('results_sha256') != clean_run.get('results_sha256')
                    or clean_run.get('fresh_output_state') != 'NO_PRIOR_SCORE_ARTIFACTS_CARRIED_INTO_THIS_RUN'
                    or any(row.get('total_score') is not None for row in clean_run.get('learners') or [])):
                raise ValueError('HOMS Assess clean-run repeatability evidence failed its provenance, repeatability, or score-hold checks')
            product_specific_refs.append(register(HOMS_ASSESS_CLEAN_RUN_REPEATABILITY))
            for path in (ROOT / 'scripts/run_homs_hymark_batch.py',
                         ROOT / clean_run.get('job_dir', '') / 'HOMS_HYMARK_BATCH_RECEIPT.json'):
                if path.is_file():
                    product_specific_refs.append(register(path))
            changes.append('The HOMS Assess batch runner now removes inherited result, mark, feedback, and receipt artifacts before scoring and records hashes for six bound source inputs. A clean Granite 3.3 run reproduced the second comparison output, while the first repeat differed; totals stayed withheld in all runs.')
            limits.append('This controlled synthetic Grade 10 comparison verifies clean-run provenance and documents model output variation, not marking accuracy. Pointwise quote gaps remain, all totals are withheld, and educator review is required.')
        if name == 'HOMS Assess' and HOMS_ASSESS_QUOTE_SUGGESTIONS.is_file():
            suggestion_evidence = read_json(HOMS_ASSESS_QUOTE_SUGGESTIONS)
            source_run = ROOT / suggestion_evidence.get('source_run', '')
            source_package_path = source_run / 'CUSTOMER_PACKAGE_RECEIPT.json'
            source_package = read_json(source_package_path)
            source_results_path = source_run / source_package['outputs']['results']
            output_paths = {key: ROOT / value for key, value in (suggestion_evidence.get('outputs') or {}).items()
                            if key in {'review_page', 'adjudication_csv', 'review_receipt', 'educator_guide', 'quality_flags_csv'}}
            review_receipt = read_json(output_paths['review_receipt'])
            if (suggestion_evidence.get('schema') != 'dio.homs.assess.pointwise_quote_suggestion_demo.v1'
                    or suggestion_evidence.get('source_results_sha256') != hashlib.sha256(source_results_path.read_bytes()).hexdigest()
                    or suggestion_evidence.get('source_package_sha256') != hashlib.sha256(source_package_path.read_bytes()).hexdigest()
                    or suggestion_evidence.get('source_totals_all_withheld') is not True
                    or suggestion_evidence.get('source_results_unchanged') is not True
                    or suggestion_evidence.get('score_mutation_performed') is not False
                    or suggestion_evidence.get('suggestions_are_unverified_not_scoring_evidence') is not True
                    or suggestion_evidence.get('suggestions_bound_to_answer_block_and_source_hashes') is not True
                    or suggestion_evidence.get('educator_decision_fields_blank') is not True
                    or suggestion_evidence.get('classroom_release_authorized') is not False
                    or suggestion_evidence.get('suggested_exact_question_scoped_span_count', 0) < 1
                    or review_receipt.get('suggestions_are_unverified_and_do_not_mutate_proposals') is not True
                    or review_receipt.get('score_mutation_performed') is not False
                    or review_receipt.get('source_results_sha256') != suggestion_evidence.get('source_results_sha256')
                    or review_receipt.get('exact_question_source_quote_suggestion_count') != suggestion_evidence.get('suggested_exact_question_scoped_span_count')
                    or review_receipt.get('withheld_score_count') != len(json.loads(source_results_path.read_text(encoding='utf-8')))
                    or any(not path.is_file() for path in output_paths.values())
                    or any(key + '_sha256' not in suggestion_evidence['outputs']
                           or hashlib.sha256(path.read_bytes()).hexdigest() != suggestion_evidence['outputs'][key + '_sha256']
                           for key, path in output_paths.items())):
                raise ValueError('HOMS Assess quote-suggestion review surface failed its source-binding, no-score, or output-integrity checks')
            for path in [HOMS_ASSESS_QUOTE_SUGGESTIONS, *output_paths.values(),
                         source_package_path, source_results_path,
                         ROOT / 'products/homs_assess_customer.py',
                         ROOT / 'scripts/build_homs_assess_quote_suggestion_demo.py']:
                product_specific_refs.append(register(path))
            changes.append('HOMS Assess now offers up to two exact sentence excerpts from the same numbered answer when a positive proposal lacks a model quote. Suggestions are ranked by memo wording, bound to the answer-block and learner-file hashes, and shown only as educator navigation aids; the CSV leaves verified quote and decision fields blank.')
            limits.append('Lexical overlap cannot determine whether a sentence substantively earns a point. The suggestions are not scoring evidence, automated totals remain withheld, and an educator must verify every point against the full response and memo.')
        if name == 'HOMS Assess' and HOMS_ASSESS_RUN_CONTEXT.is_dir():
            package_path = HOMS_ASSESS_RUN_CONTEXT / 'CUSTOMER_PACKAGE_RECEIPT.json'
            page_path = HOMS_ASSESS_RUN_CONTEXT / 'CUSTOMER_ASSESS_REVIEW.html'
            input_packet_path = OUTPUT / 'HOMS_ASSESS_RUN_CONTEXT_20261102_V1_INPUT.json'
            package = read_json(package_path)
            scoring = package.get('scoring_configuration') or {}
            results_path = HOMS_ASSESS_RUN_CONTEXT / (package.get('outputs') or {}).get('results', '')
            results = read_json(results_path)
            page = page_path.read_text(encoding='utf-8') if page_path.is_file() else ''
            expected_backend_hash = hashlib.sha256((ROOT / 'cross_folder_variants/NoEdge-Multi-Hymark-main/A_CODE/backend/server.py').read_bytes()).hexdigest()
            packet_input = read_json(input_packet_path)
            source_manifest_path = Path(packet_input['customer_packet_dir']) / 'CUSTOMER_PACKET_MANIFEST.json'
            source_rubric_path = Path(packet_input['customer_packet_dir']) / 'SOURCES/hymark_input/rubric.json'
            if not source_manifest_path.is_file():
                source_manifest_path = Path(packet_input['customer_packet_dir']) / 'manifest.json'
            if (package.get('schema') != 'dio.homs.assess.customer_execution.v1'
                    or package.get('controlled_synthetic_demo') is not True
                    or package.get('score_withholding_invariants_passed') is not True
                    or package.get('classroom_release_authorized') is not False
                    or package.get('marks_are_final') is not False
                    or package.get('withheld_score_count') != len(results)
                    or any(row.get('total_score') is not None or row.get('percentage') is not None or row.get('score_issued') is not False for row in results)
                    or scoring.get('provider') != 'ollama'
                    or scoring.get('model') != (package.get('local_provider') or {}).get('selected_model')
                    or scoring.get('temperature') != package.get('temperature')
                    or scoring.get('assessor_backend_sha256') != expected_backend_hash
                    or not source_rubric_path.is_file()
                    or scoring.get('rubric_sha256') != hashlib.sha256(source_rubric_path.read_bytes()).hexdigest()
                    or not page or str(scoring.get('model')) not in page
                    or str(scoring.get('assessor_backend_sha256')) not in page
                    or str(scoring.get('rubric_sha256')) not in page
                    or not source_manifest_path.is_file()
                    or hashlib.sha256(source_manifest_path.read_bytes()).hexdigest() != package.get('source_packet_manifest_sha256')):
                raise ValueError('HOMS Assess scoring-run context is incomplete, stale, not visible to the reviewer, or violates its held-score boundary')
            for path in (input_packet_path, package_path, page_path, results_path,
                         HOMS_ASSESS_RUN_CONTEXT / 'hymark' / Path(results_path).parent.name / 'HOMS_HYMARK_BATCH_RECEIPT.json',
                         ROOT / 'products/homs_assess_customer.py'):
                if path.is_file():
                    product_specific_refs.append(register(path))
            changes.append('The HOMS Assess review page now displays the local provider, model, temperature, seed, customer-packet fingerprint, rubric hash and assessor-backend hash. Its receipt binds these settings and the input-file hashes to the held run, making changes across runs traceable without treating proposals as issued marks.')
            limits.append('Run-context hashes support reproducibility and comparison only; they do not prove score stability or marking accuracy. Both synthetic learner totals remain withheld and qualified-educator adjudication is required.')
        if name == 'HOMS Assess' and HOMS_ASSESS_DEFINITION_CONFLICT_DEMO.is_dir():
            execution_path = HOMS_ASSESS_DEFINITION_CONFLICT_DEMO / 'CUSTOMER_EXECUTION_RECEIPT.json'
            package_path = HOMS_ASSESS_DEFINITION_CONFLICT_DEMO / 'CUSTOMER_PACKAGE_RECEIPT.json'
            execution, package = map(read_json, (execution_path, package_path))
            results_path = HOMS_ASSESS_DEFINITION_CONFLICT_DEMO / package['outputs']['results']
            results = read_json(results_path)
            learner_a = next((row for row in results if row.get('student_id') == 'learner_A'), {})
            definition_flags = [flag for flag in learner_a.get('unresolved_marking_quality_flags') or []
                                if flag.get('code') == 'answer_key_definition_conflict_review_required'
                                and flag.get('criterion') == '1.1']
            modified_packet = ROOT / 'acceptance_runs/68-product-sellability-20261027/HOMS_ASSESS_DEFINITION_CONFLICT_PROBE_20261102/CUSTOMER_PACKET'
            manifest = read_json(modified_packet / 'CUSTOMER_PACKET_MANIFEST.json')
            learner_source = (modified_packet / 'SOURCES/hymark_input/uploads/learner_A.txt').read_text(encoding='utf-8')
            if (manifest.get('packet_fingerprint') != package.get('customer_packet_fingerprint')
                    or 'Distance is the change in position from the starting point to the finishing point.' not in learner_source
                    or execution.get('external_effects') is not False
                    or package.get('withheld_score_count') != 2
                    or package.get('classroom_release_authorized') is not False
                    or len(definition_flags) != 1
                    or definition_flags[0].get('source_quote') != 'Distance is the change in position'
                    or definition_flags[0].get('conflicts') != ['distance_defined_as_endpoint_change']
                    or definition_flags[0].get('resolution_eligible') is not False
                    or any(row.get('total_score') is not None for row in results)):
                raise ValueError('HOMS Assess single-definition safeguard did not bind the misconception or preserve score withholding')
            for path in (execution_path, package_path, results_path,
                         HOMS_ASSESS_DEFINITION_CONFLICT_DEMO / package['outputs']['marks_csv'],
                         modified_packet / 'CUSTOMER_PACKET_MANIFEST.json',
                         modified_packet / 'SOURCES/hymark_input/uploads/learner_A.txt',
                         ROOT / 'scripts/run_homs_hymark_batch.py'):
                product_specific_refs.append(register(path))
            changes.append('A source-bound synthetic Grade 10 route now exercises a single reversed distance definition using the exact CAPS memo vocabulary “total path length” and “change in position.” The safeguard preserved the learner quote, flagged the 1.1 concept conflict, and withheld both learner totals; no classroom release was authorized.')
            limits.append('The safeguard detects this targeted phrasing only; it does not establish general scoring accuracy. The local provider still returned incomplete pointwise responses for both learners, and educators must review every mark and concept flag.')
        if name == 'HOMS Assess' and HOMS_ASSESS_CONFLICT_HOLD_EVIDENCE.is_file():
            evidence = read_json(HOMS_ASSESS_CONFLICT_HOLD_EVIDENCE)
            conflict_run = ROOT / evidence.get('run', '')
            execution_path = conflict_run / 'CUSTOMER_EXECUTION_RECEIPT.json'
            package_path = conflict_run / 'CUSTOMER_PACKAGE_RECEIPT.json'
            package = read_json(package_path)
            results_path = conflict_run / package['outputs']['results']
            review_path = ROOT / evidence['review_html_path']
            results = read_json(results_path)
            learner_b = next((row for row in results if row.get('student_id') == 'learner_B'), {})
            graph_flags = [flag for flag in learner_b.get('unresolved_marking_quality_flags') or []
                           if flag.get('code') == 'learner_quote_conflicts_with_motion_graph_rubric'
                           and flag.get('criterion') == '1.5']
            review_html = review_path.read_text(encoding='utf-8')
            if (digest_file(execution_path) != evidence.get('execution_receipt_sha256')
                    or digest_file(package_path) != evidence.get('package_receipt_sha256')
                    or digest_file(results_path) != evidence.get('results_sha256')
                    or digest_file(review_path) != evidence.get('review_html_sha256')
                    or digest_file(ROOT / evidence.get('customer_code', '')) != evidence.get('customer_code_sha256')
                    or package.get('withheld_score_count') != 2
                    or package.get('provisional_score_count') != 0
                    or package.get('classroom_release_authorized') is not False
                    or len(graph_flags) != 1
                    or 'MODEL PROPOSAL HELD — NOT A MARK.' not in review_html
                    or 'Unaccepted model proposal (not a mark)' not in review_html
                    or graph_flags[0].get('source_quote') not in review_html):
                raise ValueError('HOMS Assess V29 conflict-hold presentation evidence is stale or incomplete')
            for path in (HOMS_ASSESS_CONFLICT_HOLD_EVIDENCE, execution_path, package_path,
                         results_path, review_path, ROOT / evidence['customer_code']):
                product_specific_refs.append(register(path))
            changes.append('HOMS Assess now labels a directly conflicted question proposal as held and not a mark beside the exact source quote; the rubric points remain visible as unaccepted evidence for educator reassessment.')
            limits.append('V29 still proposes 12/12 on Learner B’s contradicted graph answer and leaves one separate memo point unreturned per learner. Both assessment totals are withheld, but the source-level marking-accuracy issue remains open until an educator adjudicates the affected points.')
        if name == 'HOMS Assess' and HOMS_ASSESS_MODEL_COMPARISON.is_file():
            comparison = read_json(HOMS_ASSESS_MODEL_COMPARISON)
            if comparison.get('run_state') != 'INCOMPLETE_ABORTED_FOR_EXCESSIVE_LATENCY' or comparison.get('model', {}).get('name') != 'qwen3:4b':
                raise ValueError('HOMS Assess Qwen3 comparison must remain clearly marked incomplete')
            product_specific_refs.append(register(HOMS_ASSESS_MODEL_COMPARISON))
            for artifact_row in comparison.get('partial_artifacts') or []:
                product_specific_refs.append(register(ROOT / artifact_row['path'], artifact_row.get('sha256')))
            changes.append('A controlled local Qwen3 4B comparison was stopped after more than 15 minutes with only an error-style first-learner artifact; no score-quality comparison was claimed and the model was not selected.')
            limits.append('The locally installed Qwen3 4B candidate has no completed HOMS Assess result; its observed latency/failure makes it unsuitable for the current customer path until a bounded inference configuration is established.')
        if name == 'HOMS Assess' and HOMS_ASSESS_GATE_FOLLOWUP.is_file():
            changes.append('The feedback consistency guard compares exact learner quotes with the rubric direction; current route evidence records the caught east-direction contradiction, educator-held scores, and a two-pass scoring comparison.')
            register(HOMS_ASSESS_GATE_FOLLOWUP)
        if name == 'HOMS Assess' and HOMS_ASSESS_SCORE_STABILITY.is_file():
            changes.append('Historical scorer stability evidence is retained; later identical-input comparisons found cross-run score variation and supersede any broader deterministic-stability claim.')
            register(HOMS_ASSESS_SCORE_STABILITY)
        if name == 'HOMS Assess' and HOMS_ASSESS_SCORE_WITHHOLDING.is_file():
            withholding = read_json(HOMS_ASSESS_SCORE_WITHHOLDING)
            product_specific_refs.append(register(HOMS_ASSESS_SCORE_WITHHOLDING))
            for item in withholding['artifacts']:
                product_specific_refs.append(register(ROOT / item['path'], item['sha256']))
            changes.append('The scoring route withholds numeric marks for unresolved source/feedback, motion-graph rubric conflicts, incomplete point allocations, or two-pass score mismatches. V17 withheld learner B’s proposal for a graph-concept conflict; learner A’s paired 42/50 proposal remains educator-review-only.')
            limits.append('The withholding gate prevents flagged proposals from appearing as issued scores; it does not establish the correctness of unflagged AI marks. Educator review remains required for every learner and every score.')
            disposition = 'CURRENT_HELD_EXECUTION_VERIFIED'
        if name == 'HOMS Assess' and HOMS_ASSESS_POINTWISE_COMPLETENESS.is_file():
            pointwise = read_json(HOMS_ASSESS_POINTWISE_COMPLETENESS)
            recovery_comparison = read_json(HOMS_ASSESS_POINTWISE_RECOVERY_COMPARISON)
            if (recovery_comparison.get('schema') != 'dio.homs.assess.pointwise_prompt_recovery_comparison.v1'
                    or len(recovery_comparison.get('runs', [])) != 4
                    or any(run.get('all_incomplete_totals_withheld') is not True
                           or run.get('release_authorized') is not False
                           for run in recovery_comparison.get('runs', []))):
                raise ValueError('HOMS Assess pointwise prompt/recovery comparison failed its held-score boundary')
            product_specific_refs.append(register(HOMS_ASSESS_POINTWISE_RECOVERY_COMPARISON))
            for run in recovery_comparison['runs']:
                for artifact_row in run.get('artifacts', []):
                    product_specific_refs.append(register(ROOT / artifact_row['path'], artifact_row['sha256']))
            run_dir = ROOT / pointwise.get('run', '')
            package_path = run_dir / 'CUSTOMER_PACKAGE_RECEIPT.json'
            execution_path = run_dir / 'CUSTOMER_EXECUTION_RECEIPT.json'
            if (pointwise.get('submission_count') != 2 or pointwise.get('omitted_points_defaulted_to_zero') != 0
                    or pointwise.get('all_incomplete_totals_withheld') is not True
                    or pointwise.get('marks_csv_contains_no_incomplete_proposal') is not True
                    or pointwise.get('classroom_release_authorized') is not False):
                raise ValueError('HOMS Assess V20 pointwise completeness evidence failed its withholding boundary')
            package, execution = read_json(package_path), read_json(execution_path)
            results_path = run_dir / package['outputs']['results']
            results = read_json(results_path)
            if (package.get('withheld_score_count') != 2 or package.get('provisional_score_count') != 0
                    or package.get('unreturned_point_count') != 14 or package.get('score_withholding_invariants_passed') is not True
                    or package.get('external_processing') is not False or execution.get('release_authorized') is not False
                    or execution.get('external_effects') is not False or len(results) != 2
                    or any(row.get('score_status') != 'BLOCKED_INCOMPLETE_POINTWISE_RESPONSE'
                           or row.get('total_score') is not None or row.get('percentage') is not None
                           or row.get('proposed_total_score') is not None for row in results)):
                raise ValueError('HOMS Assess V20 route emitted or retained a total despite incomplete source-bound memo point coverage')
            review_path = run_dir / package['outputs']['pointwise_educator_review']
            review_receipt_path = run_dir / package['outputs']['pointwise_review_receipt']
            review_receipt = read_json(review_receipt_path)
            if (digest_file(review_path) != review_receipt.get('page_sha256')
                    or digest_file(review_path) != package.get('pointwise_review_sha256')
                    or review_receipt.get('educator_review_required') is not True):
                raise ValueError('HOMS Assess V20 pointwise educator surface hash or review status failed')
            product_specific_refs.extend([register(HOMS_ASSESS_POINTWISE_COMPLETENESS), register(package_path), register(execution_path), register(results_path), register(review_path), register(review_receipt_path), register(run_dir / package['outputs']['marks_csv']), register(run_dir / package['outputs']['review_zip'])])
        if name == 'HOMS Assess' and HOMS_ASSESS_REVIEW_COPY_CLARITY.is_file():
            clarity = read_json(HOMS_ASSESS_REVIEW_COPY_CLARITY)
            run_dir = ROOT / clarity['run']
            package_path = run_dir / 'CUSTOMER_PACKAGE_RECEIPT.json'
            execution_path = run_dir / 'CUSTOMER_EXECUTION_RECEIPT.json'
            package = read_json(package_path)
            execution = read_json(execution_path)
            review_path = run_dir / package['outputs']['pointwise_educator_review']
            review_receipt_path = run_dir / package['outputs']['pointwise_review_receipt']
            if (clarity.get('new_copy_present') is not True or clarity.get('stale_copy_absent') is not True
                    or package.get('withheld_score_count') != 2 or package.get('provisional_score_count') != 0
                    or package.get('classroom_release_authorized') is not False
                    or execution.get('human_review_required') is not True
                    or execution.get('release_authorized') is not False
                    or execution.get('external_effects') is not False
                    or digest_file(review_path) != clarity.get('review_copy_sha256')):
                raise ValueError('HOMS Assess review copy clarification execution failed its source/hash/withholding boundary')
            product_specific_refs.extend([register(HOMS_ASSESS_REVIEW_COPY_CLARITY), register(package_path),
                                          register(execution_path), register(review_path),
                                          register(review_receipt_path),
                                          register(run_dir / package['outputs']['results']),
                                          register(run_dir / package['outputs']['marks_csv'])])
            changes.append('A fresh local synthetic Grade 10 route now states clearly that unreturned memo points remain unscored and are not inferred as zero. Both incomplete learner totals remained withheld and classroom release stayed disabled.')
            limits.append('This is a review-copy clarity improvement only. The local model still omitted 14 memo points across the two synthetic submissions; no numeric totals were issued, and scoring quality remains unresolved pending model or educator completion.')
        if name == 'HOMS Assess' and HOMS_ASSESS_QUESTION_SCOPED_REPAIR.is_file():
            repair = read_json(HOMS_ASSESS_QUESTION_SCOPED_REPAIR)
            if (repair.get('schema') != 'dio.homs.assess.question_scoped_point_repair_execution.v1'
                    or repair.get('previous_unreturned_point_count') != 14
                    or repair.get('current_unreturned_point_count') != 12
                    or repair.get('improvement_in_unreturned_point_count') != 2
                    or repair.get('withheld_score_count') != 2
                    or repair.get('classroom_release_authorized') is not False
                    or any(row.get('score_status') != 'BLOCKED_INCOMPLETE_POINTWISE_RESPONSE'
                           for row in repair.get('learners') or [])):
                raise ValueError('HOMS Assess question-scoped repair did not preserve incomplete-score holds or expected evidence')
            product_specific_refs.append(register(HOMS_ASSESS_QUESTION_SCOPED_REPAIR))
            for relative, digest in (repair.get('artifacts') or {}).items():
                product_specific_refs.append(register(ROOT / relative, digest))
            changes.append('A question-scoped missing-point recovery pass returned two additional point proposals versus the prior controlled run. It still left 12 points unreturned, so both learner totals remained withheld; no classroom release was authorized.')
            limits.append('This small-model recovery improved point coverage only modestly and did not complete either response. Returned points remain provisional, missing points remain unscored, and HOMS Assess marking quality is unresolved.')
        if name == 'HOMS Assess' and HOMS_ASSESS_STRUCTURED_POINTWISE.is_file():
            structured = read_json(HOMS_ASSESS_STRUCTURED_POINTWISE)
            learners = structured.get('learners') or []
            if (structured.get('schema') != 'dio.homs.assess.structured_pointwise_execution.v1'
                    or structured.get('previous_unreturned_point_count') != 12
                    or structured.get('current_unreturned_point_count') != 1
                    or structured.get('withheld_score_count') != 2
                    or structured.get('classroom_release_authorized') is not False
                    or len(learners) != 2
                    or any(row.get('invalid_point_ids') for row in learners)
                    or any(row.get('total_score') is not None or row.get('percentage') is not None for row in learners)):
                raise ValueError('HOMS Assess strict pointwise schema evidence failed its held-score boundary')
            product_specific_refs.append(register(HOMS_ASSESS_STRUCTURED_POINTWISE))
            for relative, digest in (structured.get('artifact_hashes') or {}).items():
                product_specific_refs.append(register(ROOT / relative, digest))
            changes.append('Strict local JSON Schema output constrained pointwise proposals to the exact memo IDs and mark ranges; unreturned points fell from 12 to 1 across the two synthetic learners. One submission is pointwise-complete, but a separate marking-quality flag blocks its total; both totals remain withheld.')
            limits.append('This is a synthetic local-model route improvement, not a scoring-accuracy claim. One point remains unreturned; the fully returned submission still has unresolved marking-quality flags, and educator review is required.')
        if name == 'HOMS Assess' and HOMS_ASSESS_TAIL_RECOVERY.is_dir():
            tail_evidence_path = HOMS_ASSESS_TAIL_RECOVERY / 'TAIL_RECOVERY_EXECUTION_EVIDENCE.json'
            tail = read_json(tail_evidence_path)
            tail_package_path = HOMS_ASSESS_TAIL_RECOVERY / 'CUSTOMER_PACKAGE_RECEIPT.json'
            tail_package = read_json(tail_package_path)
            tail_results_path = HOMS_ASSESS_TAIL_RECOVERY / tail_package['outputs']['results']
            tail_results = read_json(tail_results_path)
            if (tail.get('schema') != 'dio.homs.assess.tail_recovery_execution.v1'
                    or len(tail_results) != 2
                    or tail.get('all_total_scores_withheld') is not True
                    or tail.get('educator_review_required') is not True
                    or tail.get('classroom_release_authorized') is not False
                    or any(row.get('total_score') is not None or row.get('percentage') is not None
                           or row.get('score_status') != 'BLOCKED_MARKING_QUALITY_FLAGS'
                           for row in tail_results)
                    or any(learner.get('unreturned_point_ids') for learner in tail.get('learners') or [])):
                raise ValueError('HOMS Assess bounded residual point-recovery run failed completion or score-hold checks')
            for relative, declared_hash in tail.get('output_artifact_hashes', {}).items():
                path = HOMS_ASSESS_TAIL_RECOVERY / relative
                if not path.is_file() or digest_file(path) != declared_hash:
                    raise ValueError('HOMS Assess tail-recovery artifact hash mismatch')
            product_specific_refs.extend([
                register(tail_evidence_path), register(tail_package_path), register(tail_results_path),
                register(HOMS_ASSESS_TAIL_RECOVERY / 'CUSTOMER_EXECUTION_RECEIPT.json'),
                register(HOMS_ASSESS_TAIL_RECOVERY / tail_package['outputs']['pointwise_educator_review']),
                register(HOMS_ASSESS_TAIL_RECOVERY / tail_package['outputs']['marks_csv']),
            ])
            changes.append('One bounded, exact-ID follow-up now retries a tail of at most four unreturned memo points after grouped repair. On the controlled synthetic Grade 10 packet, it returned all memo-point IDs for both learners.')
            limits.append('Both totals remained withheld because unresolved marking-quality flags persisted (23 and 24 per learner in this run). Complete point coverage does not establish scoring accuracy; educator review remains required and classroom release is disabled.')
        if name == 'HOMS Assess' and HOMS_ASSESS_ADJUDICATION_HANDOFF.is_file():
            handoff = read_json(HOMS_ASSESS_ADJUDICATION_HANDOFF)
            handoff_dir = HOMS_ASSESS_ADJUDICATION_HANDOFF.parent
            if (handoff.get('schema') != 'dio.homs.assess.educator_adjudication_handoff_execution.v1'
                    or handoff.get('point_count') != 100
                    or handoff.get('blank_educator_fields') is not True
                    or handoff.get('unreturned_rows') != 1
                    or handoff.get('validation_state') != 'NEEDS_EDUCATOR_COMPLETION'
                    or handoff.get('validation_incomplete_points') != 100
                    or handoff.get('validation_issues') != 0
                    or handoff.get('validation_totals_calculated') is not False
                    or handoff.get('automatic_acceptance') is not False
                    or handoff.get('scores_issued') is not False
                    or handoff.get('classroom_release_authorized') is not False):
                raise ValueError('HOMS Assess educator adjudication handoff failed its blank/unissued-state boundary')
            product_specific_refs.extend([
                register(HOMS_ASSESS_ADJUDICATION_HANDOFF),
                register(handoff_dir / 'EDUCATOR_POINTWISE_ADJUDICATION.csv', handoff.get('csv_sha256')),
                register(handoff_dir / 'index.html', handoff.get('review_html_sha256')),
                register(handoff_dir / 'POINTWISE_REVIEW_RECEIPT.json', handoff.get('review_receipt_sha256')),
                register(handoff_dir / 'EDUCATOR_POINTWISE_ADJUDICATION_RECEIPT.json', handoff.get('adjudication_receipt_sha256')),
                register(handoff_dir / 'EDUCATOR_POINTWISE_ADJUDICATION_VALIDATION.json',
                         (handoff.get('artifact_hashes') or {}).get('EDUCATOR_POINTWISE_ADJUDICATION_VALIDATION.json')),
                register(handoff_dir / 'EDUCATOR_POINTWISE_ADJUDICATION_GUIDE.md', handoff.get('guide_sha256')),
                register(ROOT / 'scripts/validate_homs_assess_adjudication.py'),
            ])
            changes.append('HOMS Assess now supplies a source-bound, editable point-level educator adjudication sheet and guide with all educator fields blank. Unreturned model points are explicitly labeled unscored; editing the sheet does not issue scores or authorize release.')
            limits = [item for item in limits if 'validator checks source keys, mark bounds and reviewer decisions but does not calculate totals' not in item]
            limits.append('The generated handoff remains blank; its totals are not calculated. Any later reconciliation still requires educator decisions for every point and every source marking-quality flag; validation does not issue marks or authorize classroom release.')
            changes.append('V23 requires every memo point ID, and one bounded repair request asks only for missing point IDs. In the controlled Grade 10 Granite 3.2 comparison, the repair still omitted 14 of 100 learner-point entries; all incomplete criteria and assessment totals stayed unscored, the marks CSV exported no proposals, and a source-linked educator review surface was included in the held ZIP.')
            limits.append('The local 2B scorer still fails full point coverage despite explicit-zero prompt wording and a bounded missing-point retry. Missing points remain unscored; educator review or a more capable marking model is required. No score or classroom release was issued.')
            disposition = 'CURRENT_HELD_EXECUTION_VERIFIED'
        if name == 'HOMS Assess' and HOMS_ASSESS_RECONCILIATION_DEMO.is_file():
            reconciliation = read_json(HOMS_ASSESS_RECONCILIATION_DEMO)
            validation = reconciliation.get('completed_validation') or {}
            demo_dir = HOMS_ASSESS_RECONCILIATION_DEMO.parent
            if (reconciliation.get('schema') != 'dio.homs.assess.educator_mark_reconciliation_execution.v1'
                    or validation.get('state') != 'EDUCATOR_TOTALS_RECONCILED_REVIEW_REQUIRED'
                    or validation.get('source_point_count') != 100
                    or validation.get('totals_calculated') is not True
                    or validation.get('totals_are_reconciliation_only') is not True
                    or validation.get('unresolved_quality_flag_count') != 0
                    or reconciliation.get('ungrounded_positive_proposals_accepted_with_exact_educator_quote') != 99
                    or reconciliation.get('adversarial_guard_code') != 'UNGROUNDED_POSITIVE_ACCEPT_REQUIRES_EXACT_QUESTION_SCOPED_EDUCATOR_QUOTE'
                    or reconciliation.get('adversarial_guard_state') != 'INVALID_RETURN_REQUIRES_CORRECTION'
                    or reconciliation.get('adversarial_totals_calculated') is not False
                    or validation.get('marks_issued') is not False
                    or validation.get('classroom_release_authorized') is not False
                    or 'Synthetic' not in reconciliation.get('fixture_boundary', '')):
                raise ValueError('HOMS Assess educator total reconciliation evidence failed completeness or held-boundary checks')
            product_specific_refs.append(register(HOMS_ASSESS_RECONCILIATION_DEMO))
            for path in sorted(demo_dir.rglob('*')):
                if path.is_file():
                    product_specific_refs.append(register(path))
            for relative in ('products/homs_assess_customer.py', 'scripts/validate_homs_assess_adjudication.py',
                             'scripts/run_homs_assess_adjudication_reconciliation_demo.py'):
                product_specific_refs.append(register(ROOT / relative))
            changes.append('HOMS Assess now requires an exact quote from the learner’s question-scoped answer before an educator can accept a positive model proposal that had no bound quote. A synthetic source-bound reconciliation accepted 99 such proposals only after adding exact educator-verified quotes; a paired adversarial run removed one quote and the validator blocked the decision and withheld totals. The point/flag reconciliation remains held and issues no marks.')
            limits.append('The demonstrated completed decisions are synthetic QA values, not educator judgments and not scoring-quality evidence. Real marking still requires qualified educator review; reconciled totals remain unissued and classroom release is unauthorized.')
            product_specific_refs.extend([register(ROOT / 'products/homs_assess_customer.py'),
                                         register(ROOT / 'scripts/validate_homs_assess_adjudication.py'),
                                         register(ROOT / 'scripts/run_homs_assess_adjudication_reconciliation_demo.py')])
            disposition = 'CURRENT_HELD_EXECUTION_VERIFIED'
        if name == 'HOMS Assess' and HOMS_ASSESS_REVIEW_SOURCE_BLOCK_REFRESH.is_dir():
            refresh_path = HOMS_ASSESS_REVIEW_SOURCE_BLOCK_REFRESH / 'CUSTOMER_REVIEW_REFRESH_RECEIPT.json'
            review_receipt_path = HOMS_ASSESS_REVIEW_SOURCE_BLOCK_REFRESH / 'educator_review/POINTWISE_REVIEW_RECEIPT.json'
            if refresh_path.is_file() and review_receipt_path.is_file():
                refresh = read_json(refresh_path)
                review_receipt = read_json(review_receipt_path)
                blocks = review_receipt.get('missing_point_answer_blocks') or []
                if (refresh.get('schema') != 'dio.homs.assess.review_source_answer_block_refresh.v1'
                        or refresh.get('score_changed') is not False
                        or refresh.get('scores_issued') is not False
                        or refresh.get('classroom_release_authorized') is not False
                        or review_receipt.get('missing_point_answer_block_count') != len(blocks)
                        or review_receipt.get('educator_review_required') is not True
                        or review_receipt.get('classroom_release_authorized') is not False
                        or len(blocks) != 2):
                    raise ValueError('HOMS Assess source-answer-block review receipt failed its held-boundary checks')
                source_results = ROOT / refresh['source_results']
                if digest_file(source_results) != refresh.get('source_results_sha256'):
                    raise ValueError('HOMS Assess source-answer-block refresh no longer matches the assessment result bytes')
                results = read_json(source_results)
                for block in blocks:
                    learner = next((result for result in results if str(result.get('student_id')) == block['student_id']), None)
                    criterion = next((value for key, value in (learner or {}).get('criteria_scores', {}).items()
                                      if str(key).split(':', 1)[0].strip() == block['criterion_id']), {})
                    source_path = ROOT / block['source_file']
                    source_bytes = source_path.read_bytes()
                    start, end = block.get('byte_start'), block.get('byte_end_exclusive')
                    if (not learner or block['point_id'] not in (criterion.get('unreturned_point_ids') or [])
                            or digest_file(source_path) != block.get('source_file_sha256')
                            or block.get('coordinate_basis') != 'original_utf8_file_bytes'
                            or not isinstance(start, int) or not isinstance(end, int)
                            or hashlib.sha256(source_bytes[start:end]).hexdigest() != block.get('answer_excerpt_sha256')):
                        raise ValueError('HOMS Assess missing-point learner answer block failed source-byte verification')
                for relative, sha256 in (refresh.get('outputs') or {}).items():
                    product_specific_refs.append(register(HOMS_ASSESS_REVIEW_SOURCE_BLOCK_REFRESH / 'educator_review' / relative, sha256))
                product_specific_refs.append(register(refresh_path))
                changes.append('The educator handoff now attaches exact, source-hash and byte-span bound learner answer blocks to unreturned memo points when the submission has numbered question headings. In the latest incomplete Grade 10 route, both omitted points link to their corresponding answer blocks; both remain unscored and require educator adjudication.')
                limits.append('Question blocks only improve source navigation for human reviewers. They do not award or recommend marks, prove that a response meets a memo point, fix provider completeness, or authorize score issuance or classroom release.')
                disposition = 'CURRENT_HELD_EXECUTION_VERIFIED'
        if name == 'HOMS Assess' and HOMS_ASSESS_COMPLETE_ANSWER_SURFACE.is_dir():
            execution_path = HOMS_ASSESS_COMPLETE_ANSWER_SURFACE / 'CUSTOMER_EXECUTION_RECEIPT.json'
            package_path = HOMS_ASSESS_COMPLETE_ANSWER_SURFACE / 'CUSTOMER_PACKAGE_RECEIPT.json'
            execution, package = map(read_json, (execution_path, package_path))
            review_path = HOMS_ASSESS_COMPLETE_ANSWER_SURFACE / package['outputs']['pointwise_educator_review']
            review_receipt_path = HOMS_ASSESS_COMPLETE_ANSWER_SURFACE / package['outputs']['pointwise_review_receipt']
            review_receipt = read_json(review_receipt_path)
            blocks = review_receipt.get('criterion_answer_blocks') or []
            results_path = HOMS_ASSESS_COMPLETE_ANSWER_SURFACE / package['outputs']['results']
            results = read_json(results_path)
            expected_keys = {(learner, criterion) for learner in ('learner_A', 'learner_B')
                             for criterion in ('1.1', '1.2', '1.3', '1.4', '1.5')}
            actual_keys = {(row.get('student_id'), row.get('criterion_id')) for row in blocks}
            page_text = review_path.read_text(encoding='utf-8')
            if (execution.get('external_effects') is not False
                    or package.get('external_processing') is not False
                    or package.get('classroom_release_authorized') is not False
                    or package.get('withheld_score_count') != 2
                    or package.get('score_status_counts') != {'BLOCKED_INCOMPLETE_POINTWISE_RESPONSE': 2}
                    or review_receipt.get('criterion_answer_block_count') != 10
                    or actual_keys != expected_keys
                    or review_receipt.get('educator_review_required') is not True
                    or review_receipt.get('classroom_release_authorized') is not False
                    or len(results) != 2 or any(row.get('total_score') is not None for row in results)):
                raise ValueError('HOMS Assess complete answer surface did not preserve all source and held-score boundaries')
            for block in blocks:
                source_path = ROOT / block['source_file']
                source_bytes = source_path.read_bytes()
                start, end = block.get('byte_start'), block.get('byte_end_exclusive')
                if (block.get('coordinate_basis') != 'original_utf8_file_bytes'
                        or not isinstance(start, int) or not isinstance(end, int)
                        or digest_file(source_path) != block.get('source_file_sha256')
                        or hashlib.sha256(source_bytes[start:end]).hexdigest() != block.get('answer_block_sha256')
                        or html.escape(source_bytes[start:end].decode('utf-8')) not in page_text):
                    raise ValueError('HOMS Assess criterion answer failed byte-bound educator-surface verification')
            for path in (execution_path, package_path, results_path,
                         HOMS_ASSESS_COMPLETE_ANSWER_SURFACE / package['outputs']['marks_csv'],
                         review_path, review_receipt_path,
                         ROOT / 'products/homs_assess_customer.py'):
                product_specific_refs.append(register(path))
            changes.append('The current HOMS Assess educator page now shows the complete exact learner answer block for each numbered question beside its point proposals. Ten learner-question blocks are bound to source-file SHA-256 hashes and exact UTF-8 byte spans; proposed scoring behavior is unchanged.')
            limits.append('The complete answer blocks improve educator source review only. Both synthetic learner totals remain withheld for incomplete pointwise responses; scoring accuracy and educator acceptance remain unresolved, and classroom release is unauthorized.')
            disposition = 'CURRENT_HELD_EXECUTION_VERIFIED'
        if name == 'HOMS Assess' and HOMS_ASSESS_DISTANCE_CONFLICT_SURFACE.is_dir():
            execution_path = HOMS_ASSESS_DISTANCE_CONFLICT_SURFACE / 'CUSTOMER_EXECUTION_RECEIPT.json'
            package_path = HOMS_ASSESS_DISTANCE_CONFLICT_SURFACE / 'CUSTOMER_PACKAGE_RECEIPT.json'
            execution, package = map(read_json, (execution_path, package_path))
            results_path = HOMS_ASSESS_DISTANCE_CONFLICT_SURFACE / package['outputs']['results']
            results = read_json(results_path)
            learner_b = next((row for row in results if row.get('student_id') == 'learner_B'), {})
            conflicts = [flag for flag in learner_b.get('unresolved_marking_quality_flags') or []
                         if flag.get('code') == 'answer_key_distance_value_conflict_review_required'
                         and flag.get('criterion') == '1.1']
            flag = conflicts[0] if len(conflicts) == 1 else {}
            review_path = HOMS_ASSESS_DISTANCE_CONFLICT_SURFACE / package['outputs']['pointwise_educator_review']
            review_text = review_path.read_text(encoding='utf-8')
            modified_packet = ROOT / 'acceptance_runs/68-product-sellability-20261027/HOMS_ASSESS_DEFINITION_CONFLICT_PROBE_20261102/CUSTOMER_PACKET'
            source_path = modified_packet / 'SOURCES/hymark_input/uploads/learner_B.txt'
            source_text = source_path.read_text(encoding='utf-8')
            if (execution.get('external_effects') is not False
                    or package.get('external_processing') is not False
                    or package.get('classroom_release_authorized') is not False
                    or package.get('withheld_score_count') != 2
                    or 'Distance is 20 m' not in source_text
                    or len(conflicts) != 1
                    or flag.get('source_quote') != 'Distance is 20 m'
                    or flag.get('memo_point_id') != '1.1.P07'
                    or flag.get('learner_value_metres') != 20.0
                    or flag.get('memo_value_metres') != 24.0
                    or flag.get('resolution_eligible') is not False
                    or any(row.get('total_score') is not None for row in results)
                    or 'distance 20 m' not in review_text or '1.1.P07' not in review_text):
                raise ValueError('HOMS Assess numeric distance conflict did not bind the source disagreement or preserve the review hold')
            for path in (execution_path, package_path, results_path,
                         HOMS_ASSESS_DISTANCE_CONFLICT_SURFACE / package['outputs']['marks_csv'],
                         review_path, modified_packet / 'CUSTOMER_PACKET_MANIFEST.json', source_path,
                         ROOT / 'scripts/run_homs_hymark_batch.py'):
                product_specific_refs.append(register(path))
            changes.append('A fresh HOMS Assess route now flags a source-bound numeric conflict when Learner B states distance is 20 m while memo point 1.1.P07 specifies 24 m. The flag blocks acceptance of the proposal and names both values for educator review; it never changes a mark.')
            limits.append('The numeric conflict rule is deliberately narrow: a numbered motion answer, a memo point with an explicit calculated distance and metric unit, and a directly stated learner distance. This single synthetic case does not establish general numeric contradiction detection or scoring accuracy; totals remain withheld and classroom release is unauthorized.')
            disposition = 'CURRENT_HELD_EXECUTION_VERIFIED'
        if name == 'HOMS Assess' and HOMS_ASSESS_POINT_QUOTE_GROUNDING.is_file():
            evidence = read_json(HOMS_ASSESS_POINT_QUOTE_GROUNDING)
            source_root = ROOT / evidence['source_execution']
            source_package = read_json(source_root / 'CUSTOMER_PACKAGE_RECEIPT.json')
            result_path = source_root / source_package['outputs']['results']
            source_results = read_json(result_path)
            if (evidence.get('schema') != 'dio.homs.assess.point_quote_grounding_audit.v1'
                    or evidence.get('positive_point_proposal_count', 0) < 1
                    or evidence.get('positive_point_proposal_without_question_scoped_quote_count') != evidence.get('positive_point_proposal_count')
                    or evidence.get('prior_route_scores_issued') is not False
                    or evidence.get('score_mutation_performed') is not False
                    or evidence.get('source_results_sha256') != hashlib.sha256(result_path.read_bytes()).hexdigest()
                    or any(row.get('total_score') is not None or row.get('score_issued') is True for row in source_results)):
                raise ValueError('HOMS Assess point-quote audit failed its source lineage or no-mark-mutation boundary')
            product_specific_refs.extend([register(HOMS_ASSESS_POINT_QUOTE_GROUNDING), register(ROOT / 'scripts/audit_homs_assess_point_quote_grounding.py'), register(ROOT / 'scripts/run_homs_hymark_batch.py')])
            changes.append(f"A deterministic audit of the stored synthetic HOMS Assess route found that all {evidence['positive_point_proposal_count']} positive point proposals lacked an exact quote bound to their question's answer block. The scoring path now flags these proposals and withholds acceptance pending educator review; no mark was changed or issued.")
            limits.append('Question-scoped quotes establish traceability only, not correctness. This retrospective synthetic audit does not measure marking accuracy or replace educator judgment.')
            disposition = 'CURRENT_HELD_EXECUTION_VERIFIED'
        if name == 'HOMS Assess' and HOMS_ASSESS_POINT_QUOTE_REPAIR.is_file():
            repair = read_json(HOMS_ASSESS_POINT_QUOTE_REPAIR)
            learners = repair.get('students') or []
            if (repair.get('schema') != 'dio.homs.assess.point_quote_bounded_repair_execution.v1'
                    or repair.get('synthetic_acceptance_inputs_only') is not True
                    or len(learners) != 2
                    or repair.get('educator_review_required') is not True
                    or repair.get('classroom_release_authorized') is not False
                    or repair.get('automated_score_issued') is not False
                    or any(row.get('score_status') != 'BLOCKED_INCOMPLETE_POINTWISE_RESPONSE'
                           or row.get('total_score') is not None
                           or row.get('unresolved_positive_points_without_quote', 0) < 1
                           or row.get('pointwise_repair_used') is not True for row in learners)):
                raise ValueError('HOMS Assess quote-repair evidence failed its source-grounded hold boundary')
            product_specific_refs.extend([
                register(HOMS_ASSESS_POINT_QUOTE_REPAIR),
                register(HOMS_ASSESS_POINT_QUOTE_REPAIR.parent / 'customer-route/CUSTOMER_EXECUTION_RECEIPT.json'),
                register(HOMS_ASSESS_POINT_QUOTE_REPAIR.parent / 'customer-route/CUSTOMER_PACKAGE_RECEIPT.json'),
                register(HOMS_ASSESS_POINT_QUOTE_REPAIR.parent / 'customer-route/hymark' / next(iter((HOMS_ASSESS_POINT_QUOTE_REPAIR.parent / 'customer-route/hymark').iterdir())) / 'results.json'),
                register(ROOT / 'scripts/run_homs_hymark_batch.py'),
            ])
            changes.append('Positive memo-point proposals without exact question-scoped quotes now trigger bounded, question-only quote recovery. The synthetic local-model route did not return complete grounded repairs, so both learner totals remain blocked and no score is issued.')
            limits.append('The recovery prompt and hold behavior are verified; quote recovery did not resolve the small local model’s missing point-level evidence. Educator assessment remains required, and marking accuracy is unproved.')
            disposition = 'CURRENT_HELD_EXECUTION_VERIFIED'
        if name == 'HOMS Assess' and HOMS_ASSESS_POINT_QUOTE_REPAIR_ATTEMPTS[1].is_file():
            hymark_backend = ROOT / 'cross_folder_variants/NoEdge-Multi-Hymark-main/A_CODE/backend/server.py'
            backend_text = hymark_backend.read_text(encoding='utf-8')
            if ('For every positive point score, also include a concise verbatim quote' not in backend_text
                    or 'Point-level quotes are omitted to keep this compact' in backend_text
                    or '"required": ["score", "quotes"]' not in backend_text
                    or '"quotes": {"type": "array", "items": {"type": "string"}}' not in backend_text):
                raise ValueError('HOMS Assess provider prompt still conflicts with the exact point-quote validation gate')
            attempts = [read_json(path) for path in HOMS_ASSESS_POINT_QUOTE_REPAIR_ATTEMPTS if path.is_file()]
            if any(row.get('state') != 'STOPPED_WITHOUT_COMPLETED_CUSTOMER_ROUTE'
                   or row.get('qualification_use') != 'INCONCLUSIVE; not included as successful product evidence'
                   for row in attempts):
                raise ValueError('HOMS Assess model attempt evidence incorrectly claims a completed route')
            product_specific_refs.extend([register(hymark_backend), *[register(path) for path in HOMS_ASSESS_POINT_QUOTE_REPAIR_ATTEMPTS if path.is_file()]])
            changes.append('The HyMark pointwise system prompt now requests the exact per-point quote objects required by the HOMS validation and repair gates, removing the prior instruction conflict. Fresh larger-model route attempts did not complete; no new scoring accuracy or learner-result claim is made.')
            limits.append('The corrected point-quote contract is in place, but full-route inference has not completed with the available local models. Assessment totals remain withheld until source-grounded marks and educator review are complete.')
        if name == 'HOMS Assess' and (HOMS_ASSESS_POINT_QUOTE_REVIEW_SURFACE / 'POINT_QUOTE_REVIEW_SURFACE_EVIDENCE.json').is_file():
            quote_surface = read_json(HOMS_ASSESS_POINT_QUOTE_REVIEW_SURFACE / 'POINT_QUOTE_REVIEW_SURFACE_EVIDENCE.json')
            if (quote_surface.get('schema') != 'dio.homs.assess.pointwise_review_point_quote_surface.v1'
                    or quote_surface.get('point_row_count') != 100
                    or quote_surface.get('positive_proposals_without_question_scoped_quote') != quote_surface.get('positive_proposal_count')
                    or quote_surface.get('positive_proposals_with_exact_question_scoped_quote') != 0
                    or quote_surface.get('all_educator_decisions_blank') is not True
                    or quote_surface.get('source_quote_offsets_bound_to_learner_file') is not True
                    or quote_surface.get('classroom_release_authorized') is not False
                    or quote_surface.get('marks_issued') is not False):
                raise ValueError('HOMS Assess pointwise quote review surface failed source or no-mark boundary checks')
            product_specific_refs.extend([
                register(HOMS_ASSESS_POINT_QUOTE_REVIEW_SURFACE / 'POINT_QUOTE_REVIEW_SURFACE_EVIDENCE.json'),
                register(HOMS_ASSESS_POINT_QUOTE_REVIEW_SURFACE / 'POINTWISE_REVIEW_RECEIPT.json'),
                register(HOMS_ASSESS_POINT_QUOTE_REVIEW_SURFACE / 'EDUCATOR_POINTWISE_ADJUDICATION.csv'),
                register(HOMS_ASSESS_POINT_QUOTE_REVIEW_SURFACE / 'index.html'),
                register(ROOT / 'products/homs_assess_customer.py'),
            ])
            changes.append('The educator surface and pointwise adjudication sheet now show whether each positive point has an exact quote from the matching question, with learner-file offsets and source hash. The synthetic review surfaced all 86 positive proposals without such a quote; no marks were issued.')
            limits.append('Exact quote visibility improves reviewer traceability; it does not establish that a proposal is correct. All proposal decisions remain blank for educator review.')
        if name == 'HOMS Assess' and HOMS_ASSESS_SINGLE_QUESTION_QUOTE_PROBE.is_file():
            probe = read_json(HOMS_ASSESS_SINGLE_QUESTION_QUOTE_PROBE)
            backend_path = ROOT / 'cross_folder_variants/NoEdge-Multi-Hymark-main/A_CODE/backend/server.py'
            if (probe.get('schema') != 'dio.homs.assess.single_question_point_quote_probe.v1'
                    or probe.get('question_id') != '1.1'
                    or probe.get('expected_point_count') != 8
                    or probe.get('returned_point_count') != 8
                    or probe.get('positive_points_with_exact_question_quote') != 3
                    or probe.get('newly_grounded_positive_points_after_repair') != 0
                    or probe.get('response_complete_under_customer_gate') is not False
                    or probe.get('marks_issued') is not False
                    or probe.get('classroom_release_authorized') is not False):
                raise ValueError('HOMS Assess single-question quote probe violated the source or score-hold boundary')
            product_specific_refs.extend([
                register(HOMS_ASSESS_SINGLE_QUESTION_QUOTE_PROBE),
                register(ROOT / 'scripts/run_homs_assess_single_question_quote_probe.py'),
                register(ROOT / 'scripts/run_homs_hymark_batch.py'),
                register(backend_path),
            ])
            changes.append('The local strict output schema now requires `{score, quotes}` for each exact memo-point ID, and question-scoped repair sees only the matching answer block. The Grade 10 probe returned three exact supporting quotes out of eight points; bounded repair added none, so the production gate kept the response incomplete and issued no mark.')
            limits.append('Five positive point proposals still lack exact answer quotes, and the response remains incomplete. No assessment total is issued until all points are grounded and an educator adjudicates them.')
        if name == 'HOMS Assess' and all(path.is_file() for path in HOMS_ASSESS_GROUNDING_COMPARISON_PROBES):
            granite_probe, qwen_probe = [read_json(path) for path in HOMS_ASSESS_GROUNDING_COMPARISON_PROBES]
            common_source = ('source_answer_sha256', 'question_answer_block_sha256', 'source_rubric_sha256')
            if (any(granite_probe.get(key) != qwen_probe.get(key) for key in common_source)
                    or any(probe.get('question_id') != '1.1'
                           or probe.get('expected_point_count') != 8
                           or probe.get('response_complete_under_customer_gate') is not False
                           or probe.get('marks_issued') is not False
                           or probe.get('classroom_release_authorized') is not False
                           for probe in (granite_probe, qwen_probe))
                    or granite_probe.get('model') != 'granite3.3:2b'
                    or granite_probe.get('positive_points_with_exact_question_quote') != 3
                    or qwen_probe.get('model') != 'qwen3:4b'
                    or qwen_probe.get('positive_point_count') != 0
                    or any(point.get('score') is not None
                           for point in qwen_probe.get('normalized_proposals', {}).get('1.1', {}).get('point_scores', []))):
                raise ValueError('HOMS Assess same-question model comparison failed source-binding or score-withholding checks')
            product_specific_refs.extend(register(path) for path in HOMS_ASSESS_GROUNDING_COMPARISON_PROBES)
            changes.append('A same-answer, same-rubric HOMS Assess comparison confirmed Granite 3.3 2B produced 8 positive proposals but exact question quotes for only 3; Qwen 3 4B produced no usable point marks. Both responses failed the completion gate, and the route issued no marks.')
            limits.append('This single synthetic-question comparison is diagnostic only, not a scoring-accuracy benchmark. Neither local model completed the quote-grounding contract; educator review remains required and classroom release is unauthorized.')
        if name == 'HOMS Assess' and HOMS_ASSESS_QUESTION_SCOPED_POINTWISE.is_file():
            scoped = read_json(HOMS_ASSESS_QUESTION_SCOPED_POINTWISE)
            if (scoped.get('schema') != 'dio.homs.assess.question_scoped_pointwise_execution.v1'
                    or scoped.get('synthetic_acceptance_inputs_only') is not True
                    or len(scoped.get('students') or []) != 2
                    or scoped.get('current_unreturned_point_count') != 32
                    or scoped.get('current_positive_points_with_exact_question_quote') != 32
                    or scoped.get('all_assessment_totals_withheld') is not True
                    or scoped.get('all_scores_blocked_for_incomplete_pointwise_response') is not True
                    or scoped.get('marks_issued') is not False
                    or scoped.get('classroom_release_authorized') is not False):
                raise ValueError('HOMS Assess question-scoped route failed its completeness or no-score boundary')
            route = HOMS_ASSESS_QUESTION_SCOPED_POINTWISE.parent / 'customer-route'
            product_specific_refs.extend([
                register(HOMS_ASSESS_QUESTION_SCOPED_POINTWISE),
                register(route / 'CUSTOMER_EXECUTION_RECEIPT.json'),
                register(route / 'CUSTOMER_PACKAGE_RECEIPT.json'),
                register(route / 'hymark' / next(iter((route / 'hymark').iterdir())) / 'results.json'),
                register(ROOT / 'scripts/run_homs_hymark_batch.py'),
            ])
            changes.append('Pointwise HOMS scoring now sends one numbered answer and one criterion per local-model request, including repeatability passes. The two-learner synthetic Grade 10 route reduced unreturned point IDs from 42 to 32 and produced 32 exact quotes for positive proposals; both assessment totals remain blocked and no marks were issued.')
            limits.append('Question-scoped calls improve response completeness but still leave 32 point IDs unreturned across the two learners. Exact quotes establish traceability, not mark correctness; educator review and adjudication remain required.')
        if name == 'HOMS Assess' and HOMS_ASSESS_SMALL_CHUNK_POINTWISE.is_file():
            scoped = read_json(HOMS_ASSESS_SMALL_CHUNK_POINTWISE)
            if (scoped.get('schema') != 'dio.homs.assess.scoped_repair_prompt_execution.v1'
                    or scoped.get('synthetic_acceptance_inputs_only') is not True
                    or scoped.get('current_unreturned_points') != 16
                    or scoped.get('current_positive_points_with_exact_quote') != 50
                    or scoped.get('all_totals_withheld') is not True
                    or scoped.get('all_blocked') is not True
                    or scoped.get('marks_issued') is not False
                    or scoped.get('classroom_release_authorized') is not False):
                raise ValueError('HOMS Assess small-chunk execution failed its completeness or no-score boundary')
            route = HOMS_ASSESS_SMALL_CHUNK_POINTWISE.parent / 'customer-route'
            product_specific_refs.extend([
                register(HOMS_ASSESS_SMALL_CHUNK_POINTWISE),
                register(route / 'CUSTOMER_EXECUTION_RECEIPT.json'),
                register(route / 'CUSTOMER_PACKAGE_RECEIPT.json'),
                register(route / 'hymark' / next(iter((route / 'hymark').iterdir())) / 'results.json'),
                register(ROOT / 'scripts/run_homs_hymark_batch.py'),
            ])
            changes.append('Four-point repairs and compact scoped repair prompts reduced missing IDs from 32 to 16 across the Grade 10 synthetic route and yielded 50 positive proposals with exact answer quotes. All remaining omissions are in Question 1.3; both totals remain blocked.')
            limits.append('Question 1.3 remains incomplete for both synthetic learners. Exact quotes establish traceability, not mark correctness; no score is issued and educator review remains required.')
        if name == 'HOMS Assess' and HOMS_ASSESS_SINGLE_POINT_REPAIR.is_file():
            scoped = read_json(HOMS_ASSESS_SINGLE_POINT_REPAIR)
            if (scoped.get('schema') != 'dio.homs.assess.single_point_repair_comparison.v1'
                    or scoped.get('synthetic_acceptance_inputs_only') is not True
                    or scoped.get('baseline_unreturned_points') != 16
                    or scoped.get('current_unreturned_points') != 20
                    or scoped.get('current_positive_points_with_exact_quote') != 47
                    or scoped.get('all_totals_withheld') is not True
                    or scoped.get('all_blocked') is not True
                    or scoped.get('marks_issued') is not False
                    or scoped.get('classroom_release_authorized') is not False):
                raise ValueError('HOMS Assess single-point comparison failed its no-score boundary')
            route = HOMS_ASSESS_SINGLE_POINT_REPAIR.parent / 'customer-route'
            product_specific_refs.extend([
                register(HOMS_ASSESS_SINGLE_POINT_REPAIR),
                register(route / 'CUSTOMER_EXECUTION_RECEIPT.json'),
                register(route / 'CUSTOMER_PACKAGE_RECEIPT.json'),
                register(route / 'hymark' / next(iter((route / 'hymark').iterdir())) / 'results.json'),
                register(ROOT / 'scripts/run_homs_hymark_batch.py'),
            ])
            changes.append('A controlled comparison found that one-point repairs degraded coverage (20 unreturned versus 16 with four-point chunks, and 47 versus 50 quoted positive proposals). The route retains four-point question-scoped repairs.')
            limits.append('Both model routes remain incomplete on Question 1.3. This experiment does not establish marking accuracy; totals are withheld and educator review remains required.')
        if name == 'HOMS Assess' and HOMS_ASSESS_STRICT_POINTWISE_SCHEMA.is_file():
            scoped = read_json(HOMS_ASSESS_STRICT_POINTWISE_SCHEMA)
            if (scoped.get('schema') != 'dio.homs.assess.strict_pointwise_schema_execution.v1'
                    or scoped.get('synthetic_acceptance_inputs_only') is not True
                    or scoped.get('total_memo_point_count') != 100
                    or scoped.get('current_unreturned_point_count') != 0
                    or scoped.get('withheld_score_count') != 2
                    or scoped.get('all_totals_withheld') is not True
                    or scoped.get('marks_issued') is not False
                    or scoped.get('classroom_release_authorized') is not False):
                raise ValueError('HOMS Assess strict-schema execution failed completeness or score-withholding checks')
            route = HOMS_ASSESS_STRICT_POINTWISE_SCHEMA.parent / 'customer-route'
            product_specific_refs.extend([
                register(HOMS_ASSESS_STRICT_POINTWISE_SCHEMA),
                register(route / 'CUSTOMER_EXECUTION_RECEIPT.json'),
                register(route / 'CUSTOMER_PACKAGE_RECEIPT.json'),
                register(route / 'hymark' / next(iter((route / 'hymark').iterdir())) / 'results.json'),
                register(ROOT / 'cross_folder_variants/NoEdge-Multi-Hymark-main/A_CODE/backend/server.py'),
                register(ROOT / 'scripts/run_homs_hymark_batch.py'),
            ])
            changes.append('Local HOMS pointwise scoring now applies the strict response schema to the assessment call. The synthetic Grade 10 route returned all 100 allocated memo-point IDs, reducing omissions from 16 to zero.')
            limits.append('Both totals remain blocked by positive point proposals without exact question-scoped quotes and other marking-quality flags, including Learner B’s graph-concept conflict. Completeness does not establish marking correctness; educator adjudication is required.')
        if name == 'HOMS Assess' and HOMS_ASSESS_POSITIVE_QUOTE_SCHEMA.is_file():
            scoped = read_json(HOMS_ASSESS_POSITIVE_QUOTE_SCHEMA)
            if (scoped.get('schema') != 'dio.homs.assess.positive_quote_schema_execution.v1'
                    or scoped.get('synthetic_acceptance_inputs_only') is not True
                    or scoped.get('total_memo_point_count') != 100
                    or scoped.get('unreturned_point_count') != 0
                    or scoped.get('prior_positive_quote_flags') != 33
                    or scoped.get('current_positive_quote_flags') != 30
                    or scoped.get('withheld_score_count') != 2
                    or scoped.get('all_totals_withheld') is not True
                    or scoped.get('marks_issued') is not False
                    or scoped.get('classroom_release_authorized') is not False):
                raise ValueError('HOMS Assess positive-quote schema failed its evidence or score-withholding checks')
            route = HOMS_ASSESS_POSITIVE_QUOTE_SCHEMA.parent / 'customer-route'
            product_specific_refs.extend([
                register(HOMS_ASSESS_POSITIVE_QUOTE_SCHEMA),
                register(route / 'CUSTOMER_EXECUTION_RECEIPT.json'),
                register(route / 'CUSTOMER_PACKAGE_RECEIPT.json'),
                register(route / 'hymark' / next(iter((route / 'hymark').iterdir())) / 'results.json'),
                register(ROOT / 'cross_folder_variants/NoEdge-Multi-Hymark-main/A_CODE/backend/server.py'),
            ])
            changes.append('The strict pointwise schema now couples positive point marks to a nonempty quote list. Exact-source checks reduced missing-quote flags from 33 to 30 while all 100 point IDs remained present.')
            limits.append('Thirty positive point proposals still lack exact source quotes, and Learner B’s graph-concept conflict remains. Both totals are withheld; source traceability is not proof of correct marking.')
        if name == 'HOMS Assess' and HOMS_ASSESS_UNGROUNDED_REVIEW_CONTEXT.is_file():
            review_evidence = read_json(HOMS_ASSESS_UNGROUNDED_REVIEW_CONTEXT)
            review_csv = OUTPUT / review_evidence['adjudication_csv']
            route = OUTPUT / 'HOMS_ASSESS_GROUNDED_QUOTE_SCHEMA_20261102_V14/customer-route'
            with review_csv.open('r', encoding='utf-8-sig', newline='') as handle:
                review_rows = list(csv.DictReader(handle))
            ungrounded = [row for row in review_rows
                          if row.get('point_quote_state') == 'NO_EXACT_QUESTION_SCOPED_QUOTE'
                          and float(row.get('model_proposed_marks') or 0) > 0]
            if (review_evidence.get('schema') != 'dio.homs.assess.ungrounded_positive_review_context.v1'
                    or review_evidence.get('source_results_sha256') != digest_file(route / 'hymark' / next(iter((route / 'hymark').iterdir())) / 'results.json')
                    or len(ungrounded) != 30
                    or review_evidence.get('missing_quote_positive_proposal_count') != len(ungrounded)
                    or review_evidence.get('all_have_exact_question_block_source_excerpt') is not True
                    or review_evidence.get('all_excerpt_byte_spans_and_hashes_verified') is not True
                    or digest_file(review_csv) != review_evidence.get('adjudication_csv_sha256')
                    or any(row.get('missing_point_answer_state') != 'QUESTION_BLOCK_FOR_UNGROUNDED_POSITIVE_PROPOSAL_REVIEW'
                           or not row.get('missing_point_answer_source_excerpt') for row in ungrounded)
                    or review_evidence.get('marks_issued') is not False
                    or review_evidence.get('score_release_authorized') is not False):
                raise ValueError('HOMS Assess educator source context failed its quote-gap lineage or score-hold checks')
            for row in ungrounded:
                source = route / 'input/uploads' / f"{row['student_id']}.txt"
                data = source.read_bytes()
                start, end = int(row['missing_point_answer_byte_start']), int(row['missing_point_answer_byte_end_exclusive'])
                excerpt = data[start:end]
                if (hashlib.sha256(data).hexdigest() != row.get('missing_point_source_file_sha256')
                        or hashlib.sha256(excerpt).hexdigest() != row.get('missing_point_answer_sha256')
                        or excerpt.decode('utf-8') != row.get('missing_point_answer_source_excerpt')):
                    raise ValueError('HOMS Assess educator answer context is not bound to the exact submitted bytes')
            product_specific_refs.extend([
                register(HOMS_ASSESS_UNGROUNDED_REVIEW_CONTEXT), register(review_csv),
                register(review_csv.parent / 'index.html'),
                register(HOMS_ASSESS_UNGROUNDED_REVIEW_CONTEXT.parent / 'educator_review/POINTWISE_REVIEW_RECEIPT.json'),
                register(ROOT / 'products/homs_assess_customer.py'),
            ])
            changes.append('HOMS Assess now places the exact question-scoped learner answer block, source-file hash, byte span and excerpt hash beside each positive point proposal that lacks a valid quotation. The CSV and HTML surface all 30 quote gaps for targeted educator review.')
            limits.append('This improves review access only; it does not validate the model proposals or reduce the 30 unresolved quote flags. Both learner totals remain withheld, and no marks are issued.')
        if name == 'HOMS Assess' and HOMS_ASSESS_UNBOUND_QUOTE_DIAGNOSTICS.is_file():
            diagnostic = read_json(HOMS_ASSESS_UNBOUND_QUOTE_DIAGNOSTICS)
            route = HOMS_ASSESS_UNBOUND_QUOTE_DIAGNOSTICS.parent / 'customer-route'
            package_path = route / 'CUSTOMER_PACKAGE_RECEIPT.json'
            package = read_json(package_path)
            results_path = route / str(package['outputs']['results'])
            review_csv = route / 'educator_review/EDUCATOR_POINTWISE_ADJUDICATION.csv'
            review_receipt_path = route / 'educator_review/POINTWISE_REVIEW_RECEIPT.json'
            review_html = route / 'educator_review/index.html'
            with review_csv.open('r', encoding='utf-8-sig', newline='') as handle:
                review_rows = list(csv.DictReader(handle))
            candidate_rows = []
            states = Counter()
            for review_row in review_rows:
                try:
                    candidates = json.loads(review_row.get('model_quote_candidates_not_bound_to_question_json') or '[]')
                except json.JSONDecodeError as exc:
                    raise ValueError('HOMS Assess quote diagnostic field is not valid JSON') from exc
                if candidates:
                    candidate_rows.append(review_row)
                for candidate in candidates:
                    states[str(candidate.get('state') or '')] += 1
                    answer_path = route / 'input/uploads' / f"{review_row['student_id']}.txt"
                    answer = ' '.join(answer_path.read_text(encoding='utf-8').split())
                    if ' '.join(str(candidate.get('text') or '').split()) in answer:
                        raise ValueError('HOMS Assess diagnostic quote candidate was mislabeled as absent from the learner submission')
            if (diagnostic.get('schema') != 'dio.homs.assess.unbound_quote_diagnostics.v2'
                    or package.get('product_name') != 'HOMS Assess' or package.get('grade') != 10
                    or diagnostic.get('customer_packet_fingerprint') != package.get('customer_packet_fingerprint')
                    or diagnostic.get('results_sha256') != digest_file(results_path)
                    or diagnostic.get('customer_package_receipt_sha256') != digest_file(package_path)
                    or diagnostic.get('educator_review_csv_sha256') != digest_file(review_csv)
                    or diagnostic.get('educator_review_receipt_sha256') != digest_file(review_receipt_path)
                    or diagnostic.get('educator_review_html_sha256') != digest_file(review_html)
                    or diagnostic.get('positive_proposals_missing_question_scoped_quote') != 29
                    or diagnostic.get('diagnostic_candidate_count') != 26
                    or diagnostic.get('diagnostic_candidate_states') != {'NOT_FOUND_IN_SUBMISSION': 26}
                    or len(candidate_rows) != 26
                    or states != Counter({'NOT_FOUND_IN_SUBMISSION': 26})
                    or package.get('withheld_score_count') != 2
                    or package.get('marks_are_final') is not False
                    or package.get('classroom_release_authorized') is not False
                    or diagnostic.get('classroom_release_authorized') is not False):
                raise ValueError('HOMS Assess unbound-quote diagnostic failed source binding or score-withholding checks')
            product_specific_refs.extend([
                register(HOMS_ASSESS_UNBOUND_QUOTE_DIAGNOSTICS), register(package_path),
                register(results_path), register(review_csv), register(review_receipt_path),
                register(review_html), register(route / 'educator_review/EDUCATOR_POINTWISE_ADJUDICATION_GUIDE.md'),
                register(ROOT / 'products/homs_assess_customer.py'),
                register(ROOT / 'scripts/run_homs_hymark_batch.py'),
            ])
            changes.append('HOMS Assess preserves model-generated citation candidates that fail exact question-scoped binding, labels whether they are absent from the learner submission, and displays them only as diagnostic clues. The fresh V19 route surfaces 26 such candidates beside 29 ungrounded positive proposals.')
            limits.append('All diagnostic candidates are explicitly non-evidence. Both Grade 10 totals remain blocked by marking-quality flags; this adds review context only and does not establish scoring accuracy.')
        if name == 'HOMS Assess' and HOMS_ASSESS_QWEN_SINGLE_QUESTION_PROBE.is_file():
            probe = read_json(HOMS_ASSESS_QWEN_SINGLE_QUESTION_PROBE)
            if (probe.get('schema') != 'dio.homs.assess.single_question_model_probe.v1'
                    or probe.get('model') != 'qwen3:4b'
                    or probe.get('question_id') != '1.3'
                    or probe.get('response_complete_under_customer_gate') is not False
                    or probe.get('elapsed_seconds') < 360
                    or probe.get('marks_issued') is not False
                    or probe.get('classroom_release_authorized') is not False):
                raise ValueError('HOMS Assess Qwen single-question probe did not preserve its timeout/no-score boundary')
            product_specific_refs.extend([
                register(HOMS_ASSESS_QWEN_SINGLE_QUESTION_PROBE),
                register(ROOT / 'scripts/run_homs_hymark_batch.py'),
                register(ROOT / 'cross_folder_variants/NoEdge-Multi-Hymark-main/A_CODE/backend/server.py'),
            ])
            changes.append('A local Qwen 3 4B probe using the current pointwise schema timed out at the six-minute request boundary on one synthetic criterion and returned no assessment; it is excluded as successful product evidence.')
            limits.append('The alternate local model did not complete even a single-question call within the configured timeout. Granite remains the measured path; its full route still blocks both totals on quote-grounding and quality flags.')
        if name == 'HOMS Accreditation' and HOMS_ACCREDITATION_CUSTOMER_EVIDENCE.is_file():
            accreditation = read_json(HOMS_ACCREDITATION_CUSTOMER_EVIDENCE)
            product_specific_refs.append(register(HOMS_ACCREDITATION_CUSTOMER_EVIDENCE))
            for item in accreditation['artifacts']:
                register(ROOT / item['path'], item['sha256'])
            for item in accreditation.get('outputs', []):
                if item['path'].endswith(('.docx', '.html', 'ACCREDITATION_REVIEW_PACK.json', 'ACCREDITATION_SOURCE_BINDINGS.json')):
                    product_specific_refs.append(register(ROOT / item['path'], item['declared_sha256']))
            if HOMS_ACCREDITATION_REVIEW_MANIFEST.is_file():
                workspace_manifest = read_json(HOMS_ACCREDITATION_REVIEW_MANIFEST)
                workspace_outputs = workspace_manifest.get('outputs') or []
                workspace_hashes = {item['path']: item['sha256'] for item in workspace_outputs}
                csv_path = HOMS_ACCREDITATION_REVIEW_WORKSHEET
                worksheet_rows = list(csv.DictReader(csv_path.open(encoding='utf-8-sig', newline=''))) if csv_path.is_file() else []
                source_bindings_path = HOMS_ACCREDITATION_CUSTOMER_RUN / 'ACCREDITATION_SOURCE_BINDINGS.json'
                pack_path = HOMS_ACCREDITATION_CUSTOMER_RUN / 'accreditation_engine/ACCREDITATION_REVIEW_PACK.json'
                package_path = HOMS_ACCREDITATION_CUSTOMER_RUN / 'CUSTOMER_PACKAGE_RECEIPT.json'
                if (workspace_manifest.get('schema') != 'dio.homs.accreditation.review_workspace.v1'
                        or workspace_manifest.get('source_count') != 6
                        or workspace_manifest.get('review_row_count') != 7
                        or workspace_manifest.get('blank_decision_fields') is not True
                        or workspace_manifest.get('authority_and_applicability_verified') is not False
                        or workspace_manifest.get('accreditation_decision_created') is not False
                        or workspace_manifest.get('institutional_attestation_created') is not False
                        or workspace_manifest.get('external_release_authorized') is not False
                        or workspace_manifest.get('source_bindings_sha256') != hashlib.sha256(source_bindings_path.read_bytes()).hexdigest()
                        or workspace_manifest.get('review_pack_sha256') != hashlib.sha256(pack_path.read_bytes()).hexdigest()
                        or workspace_manifest.get('customer_package_sha256') != hashlib.sha256(package_path.read_bytes()).hexdigest()
                        or len(worksheet_rows) != 7
                        or any(row.get(key) for row in worksheet_rows for key in ('reviewer', 'reviewed_at', 'decision', 'rationale', 'follow_up'))
                        or len(workspace_hashes) != 2
                        or any(not (ROOT / rel).is_file() or hashlib.sha256((ROOT / rel).read_bytes()).hexdigest() != digest
                               for rel, digest in workspace_hashes.items())):
                    raise ValueError('HOMS Accreditation human review workspace failed source-binding, blank-field, no-authority, or output-hash checks')
                product_specific_refs.extend([register(HOMS_ACCREDITATION_REVIEW_MANIFEST),
                                              register(HOMS_ACCREDITATION_REVIEW_WORKSPACE, workspace_hashes[str(HOMS_ACCREDITATION_REVIEW_WORKSPACE.relative_to(ROOT))]),
                                              register(HOMS_ACCREDITATION_REVIEW_WORKSHEET, workspace_hashes[str(HOMS_ACCREDITATION_REVIEW_WORKSHEET.relative_to(ROOT))]),
                                              register(ROOT / 'scripts/build_homs_accreditation_review_workspace.py')])
                changes.append('HOMS Accreditation now includes a seven-row offline review workspace tied to the current framework criterion, three mapped evidence excerpts and three unmapped files; every row preserves original source hashes, while authority, applicability, reviewer decisions and release remain unresolved.')
            changes.append('A new customer packet route now requires a separately sourced framework, exact criterion quotations, and explicitly mapped records. The controlled Criterion 4 execution preserves two contested source-reported gaps and reports supplied unmapped files.')
            limits = ['The demonstrated checklist is customer-defined, not an independently verified regulator standard. Customer records remain untrusted and unknown in freshness. The current output is a preparation pack with two open gaps; no accreditation decision, attestation or external release is authorized.']
            disposition = 'CURRENT_HELD_EXECUTION_VERIFIED'
        if name == 'Document Studio Publish' and DOCUMENT_STUDIO_PUBLISH_CUSTOMER_DEMO.is_dir():
            receipt_path = DOCUMENT_STUDIO_PUBLISH_CUSTOMER_DEMO / 'CUSTOMER_PACKAGE_RECEIPT.json'
            execution_path = DOCUMENT_STUDIO_PUBLISH_CUSTOMER_DEMO / 'CUSTOMER_EXECUTION_RECEIPT.json'
            revision_evidence_path = OUTPUT / 'DOCUMENT_STUDIO_PUBLISH_LAYOUT_REVISION_20261104_V4.json'
            if not receipt_path.is_file() or not execution_path.is_file():
                raise ValueError('Document Studio Publish customer execution receipt is missing')
            publication = read_json(receipt_path)
            revision = read_json(revision_evidence_path)
            package_path = DOCUMENT_STUDIO_PUBLISH_CUSTOMER_DEMO / 'PUBLICATION_PACKAGE_MANIFEST.json'
            package = read_json(package_path)
            if (publication.get('formatting_only') is not True
                    or publication.get('external_publication_authorized') is not False
                    or not all(publication.get('source_text_preservation_checks', {}).values())
                    or revision.get('schema') != 'dio.document_studio.publish_layout_revision_evidence.v1'
                    or revision.get('source_sha256') != package.get('source', {}).get('sha256')
                    or revision.get('pdf_page_count') != 2
                    or revision.get('checks', {}).get('all_three_formats_rendered') is not True
                    or revision.get('checks', {}).get('extra_contents_page_removed') is not True
                    or revision.get('checks', {}).get('explicit_draft_markers_flagged') is not True
                    or revision.get('checks', {}).get('approval_conflict_visible_in_review_gate') is not True
                    or revision.get('external_publication_authorized') is not False
                    or package.get('source_content_review', {}).get('state') != 'OWNER_RECONCILIATION_REQUIRED'):
                raise ValueError('Document Studio Publish did not preserve its format-only/held/source-fidelity boundaries')
            for artifact_row in publication.get('artifacts', []):
                product_specific_refs.append(register(DOCUMENT_STUDIO_PUBLISH_CUSTOMER_DEMO / artifact_row['path'], artifact_row.get('sha256')))
            product_specific_refs.extend([register(receipt_path), register(package_path), register(revision_evidence_path),
                                          register(ROOT / 'scripts/run_document_studio_publish_toc_revision.py'),
                                          register(ROOT / 'products/document_studio_publish.py'),
                                          register(ROOT / 'adapters/format_core/renderer.py')])
            product_specific_refs.append(register(execution_path))
            disposition = 'CURRENT_HELD_EXECUTION_VERIFIED'
            changes.append('Document Studio Publish now omits an unpopulated automatic Contents field instead of emitting a placeholder page. The DOCX, PDF and HTML preserve the source verbatim, while the review gate flags explicit draft language that conflicts with the supplied approval statement; publication remains held for owner reconciliation.')
            limits = ['The source remains an unfinished draft despite the packet approval claim. The format-only route does not correct its wording or verify content, citations, rights or metadata; reconcile source status and complete editorial review before publication.']
        if name == 'Document Studio Edit' and DOCUMENT_STUDIO_EDIT_CUSTOMER_DEMO.is_dir():
            execution_path = DOCUMENT_STUDIO_EDIT_CUSTOMER_DEMO / 'CUSTOMER_EXECUTION_RECEIPT.json'
            if not execution_path.is_file():
                raise ValueError('Document Studio Edit customer execution receipt is missing')
            execution = read_json(execution_path)
            receipt = execution.get('receipt') or {}
            native_root = DOCUMENT_STUDIO_EDIT_CUSTOMER_DEMO / 'document_studio'
            native_receipt_path = next(native_root.rglob('DOCUMENT_STUDIO_RECEIPT.json'), None)
            if native_receipt_path is None:
                raise ValueError('Document Studio Edit native receipt is missing')
            native_receipt = read_json(native_receipt_path)
            qa_path = native_receipt_path.parent / 'DOCUMENT_STUDIO_QA.json'
            qa = read_json(qa_path) if qa_path.is_file() else {}
            processing = native_receipt.get('processing') or {}
            if processing.get('remote_inference_used') is not False or native_receipt.get('release', {}).get('delivery_released') is not False:
                raise ValueError('Document Studio Edit customer run did not preserve local-only/held boundaries')
            for artifact_row in execution.get('artifacts', []):
                path = DOCUMENT_STUDIO_EDIT_CUSTOMER_DEMO / artifact_row['path']
                if path.is_file(): register(path, artifact_row.get('sha256'))
            product_specific_refs.extend([register(execution_path), register(native_receipt_path), register(qa_path)])
            review_template_path = native_receipt_path.parent / 'TECHNICAL_EDIT_REVIEW_TEMPLATE.csv'
            review_validation_path = native_receipt_path.parent / 'TECHNICAL_EDIT_REVIEW_VALIDATION.json'
            cli_validation_path = DOCUMENT_STUDIO_EDIT_CUSTOMER_DEMO / 'TECHNICAL_EDIT_REVIEW_VALIDATION_CLI.json'
            review_validation = read_json(review_validation_path) if review_validation_path.is_file() else {}
            if (review_validation.get('state') != 'NEEDS_TECHNICAL_EDITOR_COMPLETION'
                    or review_validation.get('expected_paragraph_count') != 8
                    or review_validation.get('release_authorized') is not False):
                raise ValueError('Document Studio Edit source-bound editor review did not remain complete-row and held')
            edit_workspace = read_json(DOCUMENT_STUDIO_EDIT_REVIEW_WORKSPACE_RECEIPT)
            edit_workspace_html = DOCUMENT_STUDIO_EDIT_REVIEW_WORKSPACE.read_text(encoding='utf-8')
            if (edit_workspace.get('schema') != 'dio.document_studio_edit.technical_review_workspace.v1'
                    or edit_workspace.get('paragraph_count') != 8
                    or edit_workspace.get('provider_flag_count') != len(qa.get('provider_flags') or [])
                    or edit_workspace.get('workspace_sha256') != digest_file(DOCUMENT_STUDIO_EDIT_REVIEW_WORKSPACE)
                    or edit_workspace.get('template_sha256') != digest_file(review_template_path)
                    or edit_workspace.get('ledger_sha256') != digest_file(native_receipt_path.parent / 'CHANGE_LEDGER.csv')
                    or edit_workspace.get('client_approval_required') is not True
                    or edit_workspace.get('release_authorized') is not False
                    or edit_workspace.get('reviewer_identity_independently_verified') is not False
                    or edit_workspace.get('editorial_quality_independently_verified') is not False
                    or any((edit_workspace.get('features') or {}).get(key) is not expected for key, expected in {
                        'source_draft_side_by_side': True, 'paragraph_search': True, 'pending_filter': True,
                        'decision_accept_revise_hold': True, 'revision_sha256_generation': True,
                        'draft_save_resume_bound_to_source_and_ledger': True,
                        'browser_storage_used': False, 'network_requests': False,
                    }.items())
                    or 'localStorage' in edit_workspace_html or 'fetch(' in edit_workspace_html
                    or 'Download completed review CSV' not in edit_workspace_html
                    or 'Resume matching draft' not in edit_workspace_html):
                raise ValueError('Document Studio Edit technical review workspace is stale, unbound, or crossed its review boundary')
            product_specific_refs.extend([
                register(DOCUMENT_STUDIO_EDIT_REVIEW_WORKSPACE),
                register(DOCUMENT_STUDIO_EDIT_REVIEW_WORKSPACE_RECEIPT),
                register(ROOT / 'scripts/build_document_studio_edit_review_workspace.py'),
            ])
            for path in (review_template_path, review_validation_path, cli_validation_path, ROOT / 'scripts/validate_document_studio_edit_review.py', ROOT / 'products/document_studio_edit_review.py'):
                if path.is_file(): product_specific_refs.append(register(path))
            disposition = 'CURRENT_HELD_EXECUTION_VERIFIED'
            flags = qa.get('provider_flags') or []
            changes.append(f"A local-only customer edit execution completed on {processing.get('model') or 'the configured local model'} and rendered editable review outputs. Deterministic checks quarantined {len(flags)} provider-flagged paragraphs; a new paragraph-level technical-editor sheet binds exact source and proposed text hashes, and the validator keeps all eight decisions pending until a qualified editor records them. Approval/release remain blocked.")
            changes.append('The technical editor handoff now presents each source/draft paragraph beside its provider rationale, supports accept/revise/hold decisions, records reviewer qualification and timezone-aware review time, hashes proposed revisions in-browser, and saves/resumes a draft tied to the source, draft and change-ledger hashes. The customer review ZIP includes the workspace; editing does not update the delivered document or authorize release.')
            limits = ['This controlled short manuscript is synthetic. Automated integrity checks do not establish editorial quality; flagged paragraphs remain source-preserved, all edits require a technical editor, and no output is released.']
        if name == 'DIO AI Assurance' and DIO_AI_ASSURANCE_CONTROLLED_EXECUTION.is_dir():
            proof_path = DIO_AI_ASSURANCE_CONTROLLED_EXECUTION / 'PRODUCT_EXECUTION_PROOF.json'
            if not proof_path.is_file():
                raise ValueError('DIO AI Assurance controlled execution proof is missing')
            proof = read_json(proof_path)
            if proof.get('execution_proof_state') != 'CONTROLLED_ROUTE_PROVED' or proof.get('source_authority_scope') != 'controlled_fixture_only' or proof.get('seraph_verdict') == 'CLEAR' or proof.get('external_release') is not False:
                raise ValueError('DIO AI Assurance controlled proof exceeded its evidence/release boundary')
            for artifact_row in proof.get('artifacts', []):
                path = DIO_AI_ASSURANCE_CONTROLLED_EXECUTION / artifact_row['filename']
                if path.is_file(): product_specific_refs.append(register(path, artifact_row.get('sha256')))
            product_specific_refs.append(register(proof_path))
            disposition = 'CURRENT_HELD_EXECUTION_VERIFIED'
            changes.append(f"A fresh bounded composition run consumed an AITrustProof dossier, receipt and proof manifest in the broader assurance review; all three control-evidence states resolved as supported. Seraph returned {proof.get('seraph_verdict')} with {proof.get('seraph_coverage_state')} coverage, the human gate remains NEEDS_YOU and external release is refused.")
        if name == 'DIO AI Assurance' and DIO_AI_ASSURANCE_TELEMETRY_BINDING_DEMO.is_dir():
            evidence_path = DIO_AI_ASSURANCE_TELEMETRY_BINDING_DEMO / 'SERAPH_TELEMETRY_CASE_BINDING_EVIDENCE.json'
            assurance_path = DIO_AI_ASSURANCE_TELEMETRY_BINDING_DEMO / 'EXECUTION/DIO_AI_ASSURANCE_CUSTOMER_RECEIPT.json'
            evidence, assurance = read_json(evidence_path), read_json(assurance_path)
            review_matrix = read_json(DIO_AI_ASSURANCE_TELEMETRY_BINDING_DEMO / 'EXECUTION/DIOAIASSURANCE_REVIEW_PACK.json').get('requirement_evidence_matrix') or []
            telemetry_rows = [row for row in review_matrix if row.get('requirement_key') == 'AI-ASSURANCE-SERAPH-TELEMETRY']
            binding = assurance.get('seraph_telemetry_review', {}).get('customer_source_binding', {})
            assessment = assurance.get('seraph_telemetry_review', {}).get('assessment', {})
            if (evidence.get('schema') != 'dio.dio_ai_assurance.telemetry_case_binding_evidence.v1'
                    or evidence.get('telemetry_case_binding_state') != 'DECLARED_CASE_ID_MISMATCH'
                    or evidence.get('telemetry_chain_state') != 'INVALID_CHAIN'
                    or evidence.get('assurance_receipt_sha256') != hashlib.sha256(assurance_path.read_bytes()).hexdigest()
                    or evidence.get('telemetry_matrix_review_state') != 'CONTESTED'
                    or len(telemetry_rows) != 1 or telemetry_rows[0].get('review_state') != 'CONTESTED'
                    or binding.get('case_binding_state') != 'DECLARED_CASE_ID_MISMATCH'
                    or assessment.get('state') != 'INVALID_CHAIN'
                    or assurance.get('external_release_gate') != 'REFUSE'
                    or assurance.get('external_effects') is not False):
                raise ValueError('DIO AI Assurance Seraph case-binding evidence failed its explicit mismatch or held-release checks')
            product_specific_refs.extend([register(evidence_path), register(assurance_path), register(DIO_AI_ASSURANCE_TELEMETRY_BINDING_DEMO / 'CUSTOMER_EXECUTION_RECEIPT.json'), register(DIO_AI_ASSURANCE_TELEMETRY_BINDING_DEMO / 'NATIVE_CUSTOMER_PACKET_RECEIPT.json')])
            product_specific_refs.append(register(DIO_AI_ASSURANCE_TELEMETRY_BINDING_DEMO / 'EXECUTION/DIOAIASSURANCE_REVIEW_PACK.json'))
            changes.append('The manifest-bound Seraph telemetry source and challenge receipt are mapped into the customer evidence review matrix. A controlled synthetic wrapper case mismatch and invalid chain produce a CONTESTED telemetry row; the human gate remains NEEDS_YOU and external release is refused.')
            limits.append('The controlled mismatch example verifies file and case binding only. It does not establish telemetry signer identity, completeness, source truth, live state, or an assurance conclusion.')
            limits = ['The execution uses a controlled synthetic fixture and proves route composition only. It is not customer evidence, an assurance opinion, a compliance or control-effectiveness certification, model approval or risk acceptance; customer system sources and authorized assurance review remain required.']
        if name == 'Campaign Lab' and CAMPAIGN_LAB_CUSTOMER_DEMO.is_dir():
            package_path = CAMPAIGN_LAB_CUSTOMER_DEMO / 'CAMPAIGN_LAB_CUSTOMER_RECEIPT.json'
            execution_path = CAMPAIGN_LAB_CUSTOMER_DEMO / 'CUSTOMER_EXECUTION_RECEIPT.json'
            binding_path = CAMPAIGN_LAB_CUSTOMER_DEMO / 'CUSTOMER_SOURCE_BINDINGS.json'
            if not package_path.is_file() or not execution_path.is_file() or not binding_path.is_file():
                raise ValueError('Campaign Lab customer package/evidence receipts are incomplete')
            campaign = read_json(package_path)
            family = campaign.get('customer_family') or {}
            governance = family.get('governance') or {}
            if campaign.get('rendered_video_count', 0) < 2 or governance.get('publication') != 'held' or governance.get('spend') != 'disabled' or campaign.get('market_validation_claimed') is not False:
                raise ValueError('Campaign Lab execution is missing required media or exceeded review/spend gates')
            bindings = read_json(binding_path)
            if bindings.get('bound_field_count') != 10:
                raise ValueError('Campaign Lab customer source binding set is incomplete')
            workflow_evidence = read_json(CAMPAIGN_LAB_WORKFLOW_DEMO_EVIDENCE)
            story_path = ROOT / family['story']['path']
            story = read_json(story_path)
            workflow_image_rel = family.get('assets', {}).get('landscape_explainer_scene_03')
            video_rel = family.get('assets', {}).get('explainer_1920x1080')
            workflow_image = ROOT / workflow_image_rel if workflow_image_rel else None
            explainer_video = ROOT / video_rel if video_rel else None
            if (workflow_evidence.get('schema') != 'dio.campaign_lab.workflow_demo_refresh_evidence.v1'
                    or workflow_evidence.get('current_run') != CAMPAIGN_LAB_CUSTOMER_DEMO.relative_to(ROOT).as_posix()
                    or workflow_evidence.get('workflow_demo_scene') != 'workflow_demo'
                    or workflow_evidence.get('source_bound_claim_count') != 10
                    or workflow_evidence.get('all_output_artifacts_hash_and_size_verified') is not True
                    or workflow_evidence.get('publication_held') is not True
                    or workflow_evidence.get('spend_disabled') is not True
                    or workflow_evidence.get('product_qualification') != 'UNPROVED'
                    or 'workflow_demo' not in [row.get('role') for row in story.get('scenes') or []]
                    or workflow_image is None or not workflow_image.is_file()
                    or workflow_evidence.get('workflow_demo_image_sha256') != hashlib.sha256(workflow_image.read_bytes()).hexdigest()
                    or explainer_video is None or not explainer_video.is_file()
                    or workflow_evidence.get('explainer_video_sha256') != hashlib.sha256(explainer_video.read_bytes()).hexdigest()):
                raise ValueError('Campaign Lab workflow-demo visual or regenerated explainer evidence is incomplete')
            for artifact_row in campaign.get('artifacts', []):
                product_specific_refs.append(register(CAMPAIGN_LAB_CUSTOMER_DEMO / artifact_row['path'], artifact_row.get('sha256')))
            for path in (package_path, execution_path, binding_path, CAMPAIGN_LAB_WORKFLOW_DEMO_EVIDENCE,
                         story_path, ROOT / 'scripts/run_campaign_lab_workflow_demo_refresh.py',
                         ROOT / 'scripts/build_multichannel_campaign_factory_v3.py'):
                product_specific_refs.append(register(path))
            disposition = 'CURRENT_HELD_EXECUTION_VERIFIED'
            changes.append('Campaign Lab now renders an actual four-step source-brief → channel-copy → visual/voice → review-pack diagram in its explainer workflow scene, replacing the previous text-over-brand-only frame. The refreshed 16:9 explainer and 9:16 reel retain ten exact source-bound statements; output hashes pass, publication remains held, spend disabled, and market validation unclaimed.')
            limits = ['This controlled example is synthetic. The diagram describes the campaign production sequence; it does not show authenticated customer software operation or prove the service log, image rights, audience fit or campaign effectiveness. Human brand/content review is required before publication; no spend or external effects are authorized.']
        if name == 'Campaign Lab' and CAMPAIGN_LAB_REVIEW_SURFACE.is_dir():
            surface_path = CAMPAIGN_LAB_REVIEW_SURFACE / 'CAMPAIGN_LAB_REVIEW.html'
            surface_manifest_path = CAMPAIGN_LAB_REVIEW_SURFACE / 'CAMPAIGN_LAB_REVIEW_SURFACE_MANIFEST.json'
            if not surface_path.is_file() or not surface_manifest_path.is_file():
                raise ValueError('Campaign Lab offline review surface or manifest is missing')
            surface = read_json(surface_manifest_path)
            campaign = read_json(CAMPAIGN_LAB_CUSTOMER_DEMO / 'CAMPAIGN_LAB_CUSTOMER_RECEIPT.json')
            binding = read_json(CAMPAIGN_LAB_CUSTOMER_DEMO / 'CUSTOMER_SOURCE_BINDINGS.json')
            html_text = surface_path.read_text(encoding='utf-8')
            artifact_rows = surface.get('artifacts') or []
            artifacts_match = all(
                (CAMPAIGN_LAB_CUSTOMER_DEMO / row['path']).is_file()
                and digest_file(CAMPAIGN_LAB_CUSTOMER_DEMO / row['path']) == row.get('sha256')
                for row in artifact_rows
            )
            if (surface.get('schema') != 'dio.campaign_lab.review_surface_manifest.v1'
                    or surface.get('customer_package_sha256') != digest_file(CAMPAIGN_LAB_CUSTOMER_DEMO / 'CAMPAIGN_LAB_CUSTOMER_RECEIPT.json')
                    or surface.get('customer_execution_sha256') != digest_file(CAMPAIGN_LAB_CUSTOMER_DEMO / 'CUSTOMER_EXECUTION_RECEIPT.json')
                    or surface.get('customer_source_bindings_sha256') != digest_file(CAMPAIGN_LAB_CUSTOMER_DEMO / 'CUSTOMER_SOURCE_BINDINGS.json')
                    or surface.get('customer_brief_sha256') != binding.get('source_text_sha256')
                    or surface.get('verified_bound_statement_count') != 10
                    or surface.get('verified_artifact_count') != len(campaign.get('artifacts') or [])
                    or surface.get('artifact_hashes_checked') is not True or not artifacts_match
                    or surface.get('publication_authorized') is not False
                    or surface.get('spend_authorized') is not False
                    or surface.get('external_effects') is not False
                    or surface.get('product_qualification') != 'UNPROVED'
                    or surface.get('review_html', {}).get('sha256') != digest_file(surface_path)
                    or len(re.findall(r'<article class="asset"', html_text)) != len(artifact_rows)
                    or not all(token in html_text for token in ('Reviewer disposition', 'localStorage', 'CAMPAIGN_LAB_REVIEW_WORKSHEET.csv', '<video controls', 'Brief-bound statements'))):
                raise ValueError('Campaign Lab review surface is stale, incomplete, or crossed its held release boundary')
            product_specific_refs.extend([
                register(surface_path, surface.get('review_html', {}).get('sha256')),
                register(surface_manifest_path),
                register(ROOT / 'scripts/build_campaign_lab_customer_review.py'),
            ])
            changes.append('Campaign Lab now has a single offline reviewer workspace for its channel copy, images, storyboards, rendered videos and source bindings. Each artifact has a hash, preview/link, reviewer disposition and rationale fields, with local CSV export; publication and spend remain disabled.')
            limits.append('Reviewer entries are local notes and do not establish claims, image rights, audience suitability or campaign performance. They do not publish content or authorize spend.')
            disposition = 'CURRENT_HELD_EXECUTION_VERIFIED'
        if name == 'Agent Authority' and AGENT_AUTHORITY_CUSTOMER_DEMO.is_dir():
            package_path = AGENT_AUTHORITY_CUSTOMER_DEMO / 'AGENT_AUTHORITY_PACKAGE_RECEIPT.json'
            execution_path = AGENT_AUTHORITY_CUSTOMER_DEMO / 'CUSTOMER_EXECUTION_RECEIPT.json'
            if not package_path.is_file() or not execution_path.is_file():
                raise ValueError('Agent Authority customer execution receipts are incomplete')
            package = read_json(package_path)
            seraph = package.get('seraph_challenge') or {}
            if seraph.get('verdict') != 'HOSTILE' or seraph.get('coverage_state') != 'partial' or package.get('external_release') != 'REFUSE' or package.get('authority_created') is not False or package.get('external_effects') is not False:
                raise ValueError('Agent Authority did not preserve the hostile-input/release refusal boundary')
            for artifact_row in package.get('artifacts', []):
                path = AGENT_AUTHORITY_CUSTOMER_DEMO / artifact_row['path']
                if path.is_file(): product_specific_refs.append(register(path, artifact_row.get('sha256')))
            product_specific_refs.extend([register(package_path), register(execution_path)])
            disposition = 'CURRENT_HELD_EXECUTION_VERIFIED'
            changes.append('A customer-route run supplied a hostile instruction in an untrusted attachment and requested both draft and external-send actions. The bounded capability check refused external sending; Seraph returned HOSTILE with partial coverage, and execution/release authority remained refused.')
            limits = ['The example and telemetry are synthetic customer declarations. Seraph hash-chain checks do not establish signer identity, source authenticity, live telemetry coverage or actual deployed-agent behavior; no capability grant, approval or external action results.']
        if name == 'ContractProof' and CONTRACTPROOF_CUSTOMER_DEMO.is_dir():
            package_path = CONTRACTPROOF_CUSTOMER_DEMO / 'CONTRACTPROOF_CUSTOMER_RECEIPT.json'
            execution_path = CONTRACTPROOF_CUSTOMER_DEMO / 'CUSTOMER_EXECUTION_RECEIPT.json'
            if not package_path.is_file() or not execution_path.is_file():
                raise ValueError('ContractProof customer execution receipts are incomplete')
            package = read_json(package_path)
            processor = package.get('processor_receipt') or {}
            if package.get('proof_integrity', {}).get('verified') is not True or processor.get('internal_processing') != 'COMPLETE' or processor.get('human_fulfilment_gate') != 'NEEDS_YOU' or processor.get('external_release_gate') != 'REFUSE' or package.get('legal_opinion_created') is not False:
                raise ValueError('ContractProof customer output failed integrity or legal/release boundary checks')
            for artifact_row in package.get('artifacts', []):
                path = CONTRACTPROOF_CUSTOMER_DEMO / artifact_row['path']
                if path.is_file(): product_specific_refs.append(register(path, artifact_row.get('sha256')))
            product_specific_refs.extend([register(package_path), register(execution_path)])
            disposition = 'CURRENT_HELD_EXECUTION_VERIFIED'
            changes.append(f"A Vesper-quarantined customer packet completed proof-integrity verification and source rehydration. Evidence sufficiency is {processor.get('evidence_sufficiency_state')}; all three obligations remain NEEDS_REVIEW, the next-step handoff is draft-only, and legal/external release remains refused.")
            limits = ['The controlled example is synthetic. Customer contract/evidence statements remain unverified and all three obligation states require the contract owner and legal reviewer; integrity verification is not a legal opinion, waiver, fulfilment decision or external delivery.']
        if name == 'ChangeProof' and CHANGEPROOF_CUSTOMER_DEMO.is_dir():
            package_path = CHANGEPROOF_CUSTOMER_DEMO / 'AI_TRUST_CUSTOMER_RECEIPT.json'
            execution_path = CHANGEPROOF_CUSTOMER_DEMO / 'CUSTOMER_EXECUTION_RECEIPT.json'
            if not package_path.is_file() or not execution_path.is_file():
                raise ValueError('ChangeProof customer execution receipts are incomplete')
            package = read_json(package_path)
            seraph = package.get('seraph_challenge') or {}
            finding_ids = {str(row.get('finding_id')) for row in seraph.get('findings') or []}
            if seraph.get('verdict') != 'CONTESTED' or not {'AI-EVALUATION', 'AI-FRESHNESS', 'AI-DRIFT'}.issubset(finding_ids) or package.get('external_release') != 'REFUSE' or package.get('authority_created') is not False:
                raise ValueError('ChangeProof did not surface stale/mismatched evaluation findings or preserve refusal boundaries')
            for artifact_row in package.get('artifacts', []):
                path = CHANGEPROOF_CUSTOMER_DEMO / artifact_row['path']
                if path.is_file(): product_specific_refs.append(register(path, artifact_row.get('sha256')))
            product_specific_refs.extend([register(package_path), register(execution_path)])
            disposition = 'CURRENT_HELD_EXECUTION_VERIFIED'
            changes.append('A customer-route model-change packet produced a Seraph CONTESTED result with material evaluation, freshness and drift findings: the submitted evaluation predates the declared prompt/connector change and references the prior model fingerprint. Release remains refused.')
            limits = ['The packet is synthetic and all system/source/evaluation details remain customer-declared; Seraph did not independently inspect model artifacts or execute evaluations. The review is a change-risk signal, not model approval, production authorization or assurance certification.']
        batch_receipt_path = HISTORICAL_CUSTOMER_BATCH / 'BATCH_RECEIPT.json'
        if batch_receipt_path.is_file():
            batch = read_json(batch_receipt_path)
            batch_rows = {str(item.get('product_name')): item for item in batch.get('results', [])}
            batch_row = batch_rows.get(name)
            if batch_row:
                if batch_row.get('status') != 'EXECUTED':
                    raise ValueError(f'{name} historical customer batch entry did not execute successfully')
                customer_dir = ROOT / batch_row['output_dir']
                execution_path = customer_dir / 'CUSTOMER_EXECUTION_RECEIPT.json'
                if not execution_path.is_file() or digest_file(execution_path) != batch_row.get('customer_execution_receipt_sha256'):
                    raise ValueError(f'{name} historical customer execution receipt is missing or changed')
                execution = read_json(execution_path)
                if execution.get('requested_product') != name or execution.get('human_review_required') is not True or execution.get('release_authorized') is not False or execution.get('external_effects') is not False:
                    raise ValueError(f'{name} historical customer execution crossed a review/release boundary')
                for artifact_row in execution.get('artifacts', []):
                    relative = Path(str(artifact_row.get('path') or ''))
                    artifact_path = (customer_dir / relative).resolve()
                    if relative.is_absolute() or '..' in relative.parts or not artifact_path.is_relative_to(customer_dir.resolve()) or not artifact_path.is_file():
                        raise ValueError(f'{name} customer artifact is missing or unsafe: {relative}')
                    register(artifact_path, artifact_row.get('sha256'))
                finish = execution.get('shared_production_finish')
                if finish is not None and ([row.get('organ') for row in finish.get('organ_steps', [])] != ['format_core', 'production_studio'] or any(row.get('state') != 'PASS' for row in finish.get('organ_steps', []))):
                    raise ValueError(f'{name} shared Production Studio finish did not verify')
                product_specific_refs.append(register(execution_path))
                disposition = 'CURRENT_HELD_EXECUTION_VERIFIED'
                changes.append('The product completed a fresh source-packet execution through the catalog runner using its listed synthetic customer example. The full wrapper inventory was rehashed and the held-review/release boundary was verified.')
                limits = ['This execution uses synthetic acceptance inputs. It proves only the current bounded customer-route behavior and artifact integrity; source truth, domain conclusions, customer acceptance and professional sign-off remain unestablished. Human review is required before any consequential use.']
        obligation_batch_path = OBLIGATION_FAMILY_CUSTOMER_BATCH / 'BATCH_RECEIPT.json'
        if obligation_batch_path.is_file():
            obligation_batch = read_json(obligation_batch_path)
            obligation_rows = {str(item.get('product_name')): item for item in obligation_batch.get('results', [])}
            obligation_row = obligation_rows.get(name)
            if obligation_row:
                if obligation_row.get('status') != 'EXECUTED':
                    raise ValueError(f'{name} obligation-family customer entry did not execute successfully')
                customer_dir = ROOT / obligation_row['output_dir']
                execution_path = customer_dir / 'CUSTOMER_EXECUTION_RECEIPT.json'
                package_path = customer_dir / 'CUSTOMER_OBLIGATION_FAMILY_RECEIPT.json'
                if not execution_path.is_file() or digest_file(execution_path) != obligation_row.get('customer_execution_receipt_sha256') or not package_path.is_file():
                    raise ValueError(f'{name} obligation-family customer receipts are missing or changed')
                execution = read_json(execution_path)
                package = read_json(package_path)
                if execution.get('requested_product') != name or execution.get('human_review_required') is not True or execution.get('release_authorized') is not False or execution.get('external_effects') is not False or package.get('legal_opinion_created') is not False or package.get('external_release') != 'REFUSE' or package.get('evidence_sufficiency_state') != 'GAPS_PRESENT':
                    raise ValueError(f'{name} obligation-family output failed customer review/release boundary checks')
                for artifact_row in execution.get('artifacts', []):
                    relative = Path(str(artifact_row.get('path') or ''))
                    artifact_path = (customer_dir / relative).resolve()
                    if relative.is_absolute() or '..' in relative.parts or not artifact_path.is_relative_to(customer_dir.resolve()) or not artifact_path.is_file():
                        raise ValueError(f'{name} obligation-family artifact is missing or unsafe: {relative}')
                    register(artifact_path, artifact_row.get('sha256'))
                product_specific_refs.extend([register(package_path), register(execution_path)])
                disposition = 'CURRENT_HELD_EXECUTION_VERIFIED'
                changes.append(f"A separate native-route {name} scenario rendered {package.get('obligation_candidate_count')} source-quoted candidates into a held obligation pack with evidence sufficiency GAPS_PRESENT; no legal opinion, award/permit decision or release was created.")
                limits = ['The controlled packet is synthetic and its source/evidence assertions are not independently verified. Candidate extraction is not legal interpretation; the responsible grant, permit, policy or tender owner must review each candidate and supply authoritative, current records.']
        source_location_batch_path = OBLIGATION_FAMILY_SOURCE_LOCATION_BATCH / 'SOURCE_LOCATION_BATCH_RECEIPT.json'
        if name in {'GrantProof', 'PermitProof', 'PolicyProof', 'TenderProof'} and source_location_batch_path.is_file():
            source_batch = read_json(source_location_batch_path)
            source_row = next((row for row in source_batch.get('results') or [] if row.get('product_name') == name), None)
            if (source_batch.get('schema') != 'dio.obligation_family.source_location_batch.v1'
                    or source_batch.get('synthetic_acceptance_inputs_only') is not True
                    or source_row is None or source_row.get('status') != 'EXECUTED'
                    or source_row.get('source_quote_match_count') != source_row.get('candidate_count')
                    or source_row.get('evidence_sufficiency_state') != 'GAPS_PRESENT'
                    or source_row.get('external_release') != 'REFUSE'):
                raise ValueError(f'{name} source-location batch did not verify exact quote spans or held release')
            customer_dir = ROOT / source_row['customer_output_dir']
            for relative, expected_hash in source_row.get('artifacts', {}).items():
                artifact_path = customer_dir / relative
                if not artifact_path.is_file() or digest_file(artifact_path) != expected_hash:
                    raise ValueError(f'{name} source-location artifact is missing or changed: {relative}')
                product_specific_refs.append(register(artifact_path, expected_hash))
            product_specific_refs.extend([
                register(source_location_batch_path),
                register(ROOT / 'products/obligationfamily/customer_runner.py'),
                register(ROOT / 'products/obligationfamily/quality_presentation.py'),
                register(ROOT / 'scripts/run_obligation_family_source_location_batch.py'),
            ])
            changes.append(f"{name} now binds every synthetic obligation quote to the saved governing instrument with the instrument SHA-256, quote SHA-256, exact UTF-8 byte and character spans, and line locations; all {source_row.get('source_quote_match_count')} matches were verified against source bytes.")
            limits.append('Source coordinates establish where the supplied bytes occur, not whether a clause was interpreted correctly or is legally current. Customer instrument and evidence assertions remain untrusted, and a qualified owner must review them before reliance.')
        native_batch_path = NATIVE_PACKET_CUSTOMER_BATCH / 'BATCH_RECEIPT.json'
        if native_batch_path.is_file():
            native_batch = read_json(native_batch_path)
            native_rows = {str(item.get('product_name')): item for item in native_batch.get('results', [])}
            native_row = native_rows.get(name)
            if native_row:
                if native_row.get('status') != 'EXECUTED':
                    raise ValueError(f'{name} native customer packet entry did not execute successfully')
                customer_dir = ROOT / native_row['output_dir']
                execution_path = customer_dir / 'CUSTOMER_EXECUTION_RECEIPT.json'
                package_path = customer_dir / 'NATIVE_CUSTOMER_PACKET_RECEIPT.json'
                if not execution_path.is_file() or digest_file(execution_path) != native_row.get('customer_execution_receipt_sha256') or not package_path.is_file():
                    raise ValueError(f'{name} native customer execution receipts are missing or changed')
                execution = read_json(execution_path)
                package = read_json(package_path)
                if execution.get('requested_product') != name or execution.get('human_review_required') is not True or execution.get('release_authorized') is not False or execution.get('external_effects') is not False or package.get('release_authorized') is not False or package.get('external_effects') is not False:
                    raise ValueError(f'{name} native customer execution crossed its human/release boundary')
                native_receipt = package.get('native_receipt') or {}
                if native_receipt.get('authority_created') is not False or native_receipt.get('external_effects') is not False:
                    raise ValueError(f'{name} native processor created authority or external effects')
                if name == 'DIO RegOps':
                    regops_pack_path = customer_dir / 'EXECUTION/REGOPS_READINESS_PACK.json'
                    regops_pack = read_json(regops_pack_path)
                    trust_states = {row.get('trust_state') for row in regops_pack.get('evidence_receipt_set', [])}
                    freshness_states = {row.get('freshness_state') for row in regops_pack.get('evidence_receipt_set', [])}
                    if trust_states != {'captured_untrusted'} or freshness_states != {'unknown'} or regops_pack.get('readiness_decision', {}).get('state') != 'REFUSE':
                        raise ValueError('DIO RegOps customer evidence trust/freshness boundary is not preserved')
                    product_specific_refs.append(register(regops_pack_path))
                if name == 'DIO AI Assurance':
                    assurance_path = customer_dir / 'EXECUTION/DIO_AI_ASSURANCE_CUSTOMER_RECEIPT.json'
                    assurance = read_json(assurance_path)
                    matrix_path = customer_dir / 'EXECUTION/DIOAIASSURANCE_REVIEW_PACK.json'
                    matrix = read_json(matrix_path).get('requirement_evidence_matrix') or []
                    if (assurance.get('human_review_gate') != 'NEEDS_YOU'
                            or assurance.get('external_release_gate') != 'REFUSE'
                            or assurance.get('seraph_verdict') == 'CLEAR'
                            or assurance.get('seraph_coverage_state') != 'partial'
                            or any(assurance.get(key) is not False for key in (
                                'assurance_opinion_created', 'compliance_certification_created',
                                'control_effectiveness_certification_created', 'model_approval_created',
                                'risk_acceptance_created', 'authority_created', 'external_effects'))
                            or any(row.get('review_state') != 'UNKNOWN' for row in matrix)
                            or any(binding.get('trust_state') != 'captured_untrusted' or binding.get('freshness_state') != 'unknown'
                                   for row in matrix for binding in row.get('source_provenance') or [])):
                        raise ValueError('DIO AI Assurance customer composition promoted source trust, certainty, or authority')
                    product_specific_refs.extend([register(assurance_path), register(matrix_path)])
                if name == 'DossierOps':
                    forbidden = native_receipt.get('forbidden_outcomes_created') or {}
                    if native_receipt.get('external_release_gate') != 'REFUSE' or any(forbidden.values()):
                        raise ValueError('DossierOps customer output created a forbidden outcome or release')
                    studio_receipt_path = next(customer_dir.rglob('DOCUMENT_STUDIO_RECEIPT.json'), None)
                    if studio_receipt_path is None or read_json(studio_receipt_path).get('processing', {}).get('remote_inference_used') is not False:
                        raise ValueError('DossierOps upstream Document Studio was not verified as local inference')
                    product_specific_refs.append(register(studio_receipt_path))
                if name == 'Offer Lab' and native_receipt.get('market_validation_claimed') is not False:
                    raise ValueError('Offer Lab customer hypothesis improperly claims market validation')
                if name == 'Market Radar' and (native_receipt.get('market_demand_claimed') is not False or native_receipt.get('customer_outreach_performed') is not False or native_receipt.get('source_count', 0) < 1):
                    raise ValueError('Market Radar customer brief lacks source captures or crossed its research-only boundary')
                if name == 'Market Radar' and MARKET_RADAR_CURRENT_ROUTE.is_dir():
                    evidence = read_json(MARKET_RADAR_CURRENT_EVIDENCE)
                    route_receipt_path = MARKET_RADAR_CURRENT_ROUTE / 'NATIVE_CUSTOMER_PACKET_RECEIPT.json'
                    package = read_json(route_receipt_path)
                    brief_path = MARKET_RADAR_CURRENT_ROUTE / 'EXECUTION/MARKET_RADAR_TARGET_BRIEF.json'
                    brief = read_json(brief_path)
                    if (evidence.get('schema') != 'dio.market_radar.ip_pinned_customer_refresh_evidence.v1'
                            or evidence.get('execution_receipt_sha256') != hashlib.sha256(route_receipt_path.read_bytes()).hexdigest()
                            or evidence.get('brief_sha256') != hashlib.sha256(brief_path.read_bytes()).hexdigest()
                            or evidence.get('source_count') != 3
                            or evidence.get('all_output_hashes_and_sizes_verified') is not True
                            or evidence.get('all_extracted_facts_reproduced_from_source_bytes') is not True
                            or evidence.get('market_demand_claimed') is not False
                            or evidence.get('customer_outreach_performed') is not False
                            or evidence.get('product_qualification') != 'UNPROVED'
                            or package.get('product_name') != 'Market Radar'
                            or package.get('route') != 'market_radar_raw'
                            or package.get('terminal_artifact_kind') != 'source_bound_market_brief'
                            or package.get('native_receipt', {}).get('source_count') != 3
                            or package.get('native_receipt', {}).get('source_failures')
                            or package.get('native_receipt', {}).get('authority_created') is not False
                            or brief.get('source_count') != 3 or brief.get('source_failures')):
                        raise ValueError('Market Radar current pinned-source refresh failed its customer route or evidence-boundary checks')
                    source_ids = {row.get('source_id') for row in brief.get('sources') or []}
                    evidence_sources = evidence.get('source_records') or []
                    if source_ids != {'ZA-COMPLY-001', 'ZA-FILESAFE-001', 'ZA-CAPECOM-001'} or len(evidence_sources) != 3:
                        raise ValueError('Market Radar current-source refresh is missing expected customer-scoped sources')
                    if any(row.get('transport') != 'HTTPS public-IP-pinned GET; TLS hostname verified; redirects refused'
                           or not row.get('resolved_ip') or row.get('facts_reproduced_from_capture') is not True
                           for row in evidence_sources):
                        raise ValueError('Market Radar source evidence does not establish pinned transport and fact reproduction')
                    product_specific_refs.extend([register(MARKET_RADAR_CURRENT_EVIDENCE), register(route_receipt_path),
                                                  register(brief_path), register(ROOT / 'scripts/run_market_radar_ip_pinned_refresh.py'),
                                                  register(ROOT / 'products/market_radar_research.py')])
                    for artifact_row in package.get('artifacts') or []:
                        product_specific_refs.append(register(MARKET_RADAR_CURRENT_ROUTE / artifact_row['path'], artifact_row.get('sha256')))
                    changes.append('Market Radar now pins each source connection to a validated public IP, verifies TLS against the requested hostname, and refuses redirects. A fresh manifest-bound customer run captured all three scoped vendor/survey pages; structured facts reproduce from the captured bytes, and source/output hashes are recorded while market demand remains unclaimed.')
                    limits.append('Source pages and extracted vendor statements are observations, not independently verified vendor performance or a complete market census. Customer context was not independently authenticated, and the run includes no interviews, demand, willingness-to-pay or product-fit proof.')
                if name == 'Opportunity Foundry':
                    opportunity_path = customer_dir / 'EXECUTION/RANKED_OPPORTUNITY_HYPOTHESES.json'
                    opportunity = read_json(opportunity_path)
                    if opportunity.get('market_demand_claimed') is not False or opportunity.get('capability_created') is not False or opportunity.get('willingness_to_pay_proved') is not False:
                        raise ValueError('Opportunity Foundry promoted a hypothesis into a market or capability claim')
                    product_specific_refs.append(register(opportunity_path))
                if name in {'CPDProof', 'PromotionProof'}:
                    profile_receipt = native_receipt.get('profile_receipt') or {}
                    forbidden = profile_receipt.get('forbidden_outcomes_created') or {}
                    if native_receipt.get('human_review_gate') != 'NEEDS_YOU' or native_receipt.get('external_release_gate') != 'REFUSE' or any(forbidden.values()):
                        raise ValueError(f'{name} VAMP profile crossed its human decision boundary')
                    product_specific_refs.append(register(customer_dir / 'EXECUTION/PROFESSIONAL_VAMP_PIPELINE_RECEIPT.json'))
                if name == 'CPDProof' and CPDPROOF_ATTACHMENT_DATE_REVIEW_DEMO.is_dir():
                    review_path = CPDPROOF_ATTACHMENT_DATE_REVIEW_DEMO / 'EXECUTION/CPDPROOF_ATTACHMENT_DATE_REVIEW.json'
                    review_html = review_path.with_suffix('.html')
                    native_path = CPDPROOF_ATTACHMENT_DATE_REVIEW_DEMO / 'NATIVE_CUSTOMER_PACKET_RECEIPT.json'
                    execution_path = CPDPROOF_ATTACHMENT_DATE_REVIEW_DEMO / 'CUSTOMER_EXECUTION_RECEIPT.json'
                    pipeline_path = CPDPROOF_ATTACHMENT_DATE_REVIEW_DEMO / 'EXECUTION/PROFESSIONAL_VAMP_PIPELINE_RECEIPT.json'
                    review, date_review_native_package, date_review_execution, date_review_pipeline = map(read_json, (review_path, native_path, execution_path, pipeline_path))
                    flagged_dates = [candidate for row in review.get('records', []) for candidate in row.get('event_date_candidates', [])
                                     if candidate.get('declared_window_comparison') == 'OUTSIDE_DECLARED_WINDOW_CANDIDATE']
                    if (review.get('schema') != 'dio.cpdproof.attachment_date_review.v1'
                            or review.get('date_candidate_count') != 1 or review.get('outside_window_candidate_count') != 1
                            or len(flagged_dates) != 1 or flagged_dates[0].get('date_iso') != '2025-12-20'
                            or flagged_dates[0].get('verified_event_date') is not False
                            or review.get('cpd_credit_awarded') is not False or review.get('cpd_compliance_certified') is not False
                            or review.get('source_trust_state') != 'CAPTURED_UNTRUSTED'
                            or date_review_execution.get('external_effects') is not False or date_review_native_package.get('release_authorized') is not False
                            or date_review_pipeline.get('external_release_gate') != 'REFUSE'
                            or not review_html.is_file()):
                        raise ValueError('CPDProof attachment date review did not preserve exact-source and professional decision boundaries')
                    for path in (review_path, review_html, native_path, execution_path, pipeline_path):
                        product_specific_refs.append(register(path))
                    for path in (ROOT / 'products/cpdproof_attachment_date_review.py',
                                 ROOT / 'products/professional_evidence_final_compat.py',
                                 ROOT / 'products/professional_evidence_projection.py'):
                        product_specific_refs.append(register(path))
                    changes.append('CPDProof now scans manifest-bound UTF-8 text attachments for ISO date candidates, byte-binds each match to its original file and compares it with the customer-declared review period. The synthetic out-of-window certificate is surfaced for human review; source trust stays unverified and no CPD credit or compliance conclusion is issued.')
                    limits.append('Date extraction covers only bounded UTF-8 text files and flags candidates, not verified event dates. Certificate authenticity, provider accreditation, point values and professional CPD decisions still require source review; external release remains refused.')
                if name == 'CPDProof' and CPDPROOF_POINT_RECONCILIATION_DEMO.is_dir():
                    root = CPDPROOF_POINT_RECONCILIATION_DEMO
                    route = root / 'customer-route'
                    review_path = route / 'EXECUTION/CPDPROOF_ATTACHMENT_DATE_REVIEW.json'
                    review_html = review_path.with_suffix('.html')
                    evidence_path = root / 'CPD_POINT_CANDIDATE_LINEAGE_EVIDENCE.json'
                    review, lineage = read_json(review_path), read_json(evidence_path)
                    reconciliation = review.get('point_candidate_reconciliation') or {}
                    if (review.get('schema') != 'dio.cpdproof.attachment_date_and_points_review.v1'
                            or review.get('attachment_point_candidate_count') != 2
                            or len(review.get('register_point_candidates') or []) != 4
                            or reconciliation.get('annual_requirement_candidate') != 25
                            or reconciliation.get('submitted_log_claim_candidate') != 29
                            or reconciliation.get('register_certificate_support_candidate') != 21
                            or reconciliation.get('attachment_points_outside_window_candidate') != 6
                            or reconciliation.get('attachment_points_without_date_candidate') != 21
                            or reconciliation.get('claim_minus_register_support_candidate') != 8
                            or reconciliation.get('register_support_minus_requirement_candidate') != -4
                            or reconciliation.get('unvalued_activity_record_ids') != ['R-06']
                            or reconciliation.get('verified') is not False
                            or lineage.get('schema') != 'dio.cpdproof.point_candidate_lineage_audit.v1'
                            or lineage.get('all_candidate_spans_verified') is not True
                            or lineage.get('cpd_credit_awarded') is not False
                            or lineage.get('cpd_compliance_certified') is not False
                            or review.get('cpd_credit_awarded') is not False
                            or review.get('cpd_compliance_certified') is not False
                            or not review_html.is_file()):
                        raise ValueError('CPDProof point-value reconciliation failed source-lineage or no-award boundaries')
                    for path in (review_path, review_html, evidence_path,
                                 route / 'CUSTOMER_EXECUTION_RECEIPT.json',
                                 route / 'NATIVE_CUSTOMER_PACKET_RECEIPT.json',
                                 route / 'EXECUTION/PROFESSIONAL_VAMP_PIPELINE_RECEIPT.json'):
                        product_specific_refs.append(register(path))
                    for path in (ROOT / 'products/cpdproof_attachment_date_review.py',
                                 ROOT / 'products/professional_evidence_final_compat.py',
                                 ROOT / 'products/professional_evidence_projection.py'):
                        product_specific_refs.append(register(path))
                    changes.append('CPDProof now shows requirement, log-claim and certificate-support candidates beside byte-bound attachment point values and date-window candidates. The controlled case exposes the 29-versus-21 candidate gap, six points tied to an outside-window activity, 21 undated attachment points and a webinar record with no accredited value.')
                    limits.append('All extracted numbers and dates remain captured-untrusted candidates. No CPD credit or compliance is awarded; certificate authenticity, accreditation, event dates and professional interpretation require review.')
                if name == 'CPDProof' and CPDPROOF_PDF_ATTACHMENT_REVIEW.is_dir():
                    evidence_path = CPDPROOF_PDF_ATTACHMENT_REVIEW / 'CPDPROOF_PDF_ATTACHMENT_REVIEW_EVIDENCE.json'
                    evidence = read_json(evidence_path)
                    native_path = CPDPROOF_PDF_ATTACHMENT_REVIEW / evidence['native_route_receipt']
                    review_path = CPDPROOF_PDF_ATTACHMENT_REVIEW / evidence['review_report']
                    review_html = CPDPROOF_PDF_ATTACHMENT_REVIEW / evidence['review_html']
                    native_package, review = read_json(native_path), read_json(review_path)
                    packet_manifest_path = CPDPROOF_PDF_ATTACHMENT_REVIEW / 'CUSTOMER_PACKET/CUSTOMER_PACKET_MANIFEST.json'
                    manifest = read_json(packet_manifest_path)
                    attachment_path = CPDPROOF_PDF_ATTACHMENT_REVIEW / 'CUSTOMER_PACKET' / evidence['attachment_path']
                    attachment_hash = digest_file(attachment_path)
                    record = next((row for row in review.get('records', []) if row.get('record_id') == 'R-05'), {})
                    date_candidate = evidence.get('event_date_candidate') or {}
                    point_candidate = evidence.get('point_value_candidate') or {}
                    from pypdf import PdfReader
                    page_text = PdfReader(str(attachment_path), strict=True).pages[int(date_candidate.get('page_number') or 1)-1].extract_text() or ''
                    date_start, date_end = int(date_candidate.get('page_text_char_start', -1)), int(date_candidate.get('page_text_char_end_exclusive', -1))
                    point_start, point_end = int(point_candidate.get('page_text_char_start', -1)), int(point_candidate.get('page_text_char_end_exclusive', -1))
                    date_span = page_text[date_start:date_end] if 0 <= date_start <= date_end <= len(page_text) else ''
                    point_span = page_text[point_start:point_end] if 0 <= point_start <= point_end <= len(page_text) else ''
                    declared_pdf = next((row for row in manifest.get('files', []) if row.get('path') == evidence['attachment_path']), {})
                    if (evidence.get('schema') != 'dio.cpdproof.pdf_attachment_review_execution.v1'
                            or native_package.get('product_name') != 'CPDProof'
                            or native_package.get('packet_fingerprint') != manifest.get('packet_fingerprint')
                            or native_package.get('release_authorized') is not False
                            or native_package.get('external_effects') is not False
                            or native_package.get('human_review_required') is not True
                            or review.get('packet_fingerprint') != manifest.get('packet_fingerprint')
                            or record.get('extraction_state') != 'PDF_TEXT_CANDIDATES_EXTRACTED'
                            or date_candidate.get('date_iso') != '2025-12-20'
                            or date_candidate.get('declared_window_comparison') != 'OUTSIDE_DECLARED_WINDOW_CANDIDATE'
                            or date_candidate.get('verified_event_date') is not False
                            or point_candidate.get('value') != 6
                            or point_candidate.get('declared_window_comparison') != 'OUTSIDE_DECLARED_WINDOW_CANDIDATE'
                            or point_candidate.get('verified_point_value') is not False
                            or evidence.get('attachment_sha256') != attachment_hash
                            or declared_pdf.get('sha256') != attachment_hash
                            or date_candidate.get('source_file_sha256') != attachment_hash
                            or point_candidate.get('source_file_sha256') != attachment_hash
                            or hashlib.sha256(page_text.encode('utf-8')).hexdigest() != date_candidate.get('page_text_sha256')
                            or date_candidate.get('page_text_sha256') != point_candidate.get('page_text_sha256')
                            or date_span != '2025-12-20' or point_span != '6'
                            or hashlib.sha256(date_span.encode('utf-8')).hexdigest() != date_candidate.get('source_span_sha256')
                            or hashlib.sha256(point_span.encode('utf-8')).hexdigest() != point_candidate.get('source_span_sha256')
                            or digest_file(native_path) != evidence.get('native_route_receipt_sha256')
                            or digest_file(review_path) != evidence.get('review_report_sha256')
                            or digest_file(review_html) != evidence.get('review_html_sha256')
                            or evidence.get('ocr_performed') is not False
                            or evidence.get('cpd_credit_awarded') is not False
                            or evidence.get('cpd_compliance_certified') is not False
                            or evidence.get('external_release_authorized') is not False):
                        raise ValueError('CPDProof PDF attachment failed manifest, page-citation, or no-award checks')
                    product_specific_refs.extend([
                        register(evidence_path), register(native_path),
                        register(CPDPROOF_PDF_ATTACHMENT_REVIEW / 'NATIVE_ROUTE/EXECUTION/PROFESSIONAL_VAMP_PIPELINE_RECEIPT.json'),
                        register(CPDPROOF_PDF_ATTACHMENT_REVIEW / 'NATIVE_ROUTE/EXECUTION/vamp_snapshot/PRO-CPDPROOF/PRO-CPDPROOF_VAMP_EVIDENCE_SNAPSHOT.zip'),
                        register(packet_manifest_path), register(CPDPROOF_PDF_ATTACHMENT_REVIEW / 'CUSTOMER_PACKET/SOURCES/02_evidence_register.csv'),
                        register(attachment_path), register(review_path), register(review_html),
                        register(ROOT / 'products/cpdproof_attachment_date_review.py'),
                    ])
                    changes.append('CPDProof now completes a native manifest-bound route with a synthetic PDF certificate. Its page-text report extracts the 2025-12-20 date and six-point claim with exact page-local coordinates, classifies both against the declared window, and performs no OCR.')
                    limits.append('Date and point values are unverified text candidates from a synthetic PDF; no CPD credit or compliance is awarded. Certificate authenticity, accreditation, activity eligibility and professional interpretation remain for human review.')
                if name == 'PromotionProof' and PROMOTIONPROOF_ATTACHMENT_RECONCILIATION_DEMO.is_dir():
                    report_path = PROMOTIONPROOF_ATTACHMENT_RECONCILIATION_DEMO / 'EXECUTION/PROMOTIONPROOF_ATTACHMENT_RECONCILIATION.json'
                    report_html = report_path.with_suffix('.html')
                    native_path = PROMOTIONPROOF_ATTACHMENT_RECONCILIATION_DEMO / 'NATIVE_CUSTOMER_PACKET_RECEIPT.json'
                    execution_path = PROMOTIONPROOF_ATTACHMENT_RECONCILIATION_DEMO / 'CUSTOMER_EXECUTION_RECEIPT.json'
                    pipeline_path = PROMOTIONPROOF_ATTACHMENT_RECONCILIATION_DEMO / 'EXECUTION/PROFESSIONAL_VAMP_PIPELINE_RECEIPT.json'
                    report, native_package, execution_receipt, pipeline_receipt = map(read_json, (report_path, native_path, execution_path, pipeline_path))
                    counts = report.get('count_reconciliation_candidate') or {}
                    period = report.get('period_coverage_candidate') or {}
                    register_path = PROMOTIONPROOF_ATTACHMENT_RECONCILIATION_DEMO / 'CUSTOMER_PACKET/SOURCES/02_evidence_register.csv'
                    register_bytes = register_path.read_bytes()
                    source_count = (report.get('attachment_records') or [{}])[0]
                    source_ref = str(source_count.get('source_ref') or '').replace('customer-packet://', 'CUSTOMER_PACKET/')
                    attachment_path = PROMOTIONPROOF_ATTACHMENT_RECONCILIATION_DEMO / source_ref
                    attachment_record = read_json(PROMOTIONPROOF_ATTACHMENT_RECONCILIATION_DEMO / 'CUSTOMER_PACKET/CUSTOMER_PACKET_MANIFEST.json')
                    declared_hash = next((row.get('sha256') for row in attachment_record.get('files', []) if row.get('path') == source_ref.removeprefix('CUSTOMER_PACKET/')), None)
                    attachment_candidates = source_count.get('count_candidates') or []
                    attachment_bytes = attachment_path.read_bytes()
                    candidate = attachment_candidates[0] if attachment_candidates else {}
                    candidate_start = int(candidate.get('source_byte_start', -1))
                    candidate_end = int(candidate.get('source_byte_end_exclusive', -1))
                    candidate_span = attachment_bytes[candidate_start:candidate_end] if 0 <= candidate_start <= candidate_end <= len(attachment_bytes) else b''
                    register_candidate = (report.get('register_count_candidates', {}).get('institutional_export') or [{}])[0]
                    register_start = int(register_candidate.get('source_byte_start', -1))
                    register_end = int(register_candidate.get('source_byte_end_exclusive', -1))
                    register_span = register_bytes[register_start:register_end] if 0 <= register_start <= register_end <= len(register_bytes) else b''
                    if (report.get('schema') != 'dio.promotionproof.attachment_reconciliation.v1'
                            or counts.get('cv_publication_count') != 11 or counts.get('register_export_count') != 9
                            or counts.get('attachment_count') != 9 or counts.get('cv_to_export_difference') != 2
                            or counts.get('register_export_matches_attachment_candidate') is not True
                            or counts.get('verified') is not False or period.get('multi_year_coverage_established') is not False
                            or period.get('required_year_span_candidate') != 3 or not attachment_candidates
                            or attachment_candidates[0].get('verified_value') is not False
                            or candidate_span != str(candidate.get('value')).encode('utf-8')
                            or candidate.get('source_file_sha256') != digest_file(attachment_path)
                            or candidate.get('source_span_sha256') != hashlib.sha256(candidate_span).hexdigest()
                            or register_span != str(register_candidate.get('value')).encode('utf-8')
                            or register_candidate.get('source_span_sha256') != hashlib.sha256(register_span).hexdigest()
                            or digest_file(attachment_path) != declared_hash
                            or digest_file(register_path) != report['register_count_candidates']['institutional_export'][0]['source_file_sha256']
                            or report_html.is_file() is False or execution_receipt.get('external_effects') is not False
                            or native_package.get('release_authorized') is not False or pipeline_receipt.get('external_release_gate') != 'REFUSE'):
                        raise ValueError('PromotionProof attachment reconciliation failed source-binding or held-decision checks')
                    for path in (report_path, report_html, native_path, execution_path, pipeline_path, register_path, attachment_path,
                                 ROOT / 'products/promotionproof_attachment_reconciliation.py',
                                 ROOT / 'products/professional_evidence_final_compat.py'):
                        product_specific_refs.append(register(path))
                    changes.append('PromotionProof now extracts and byte-binds count candidates from the customer evidence register and a manifest-bound institutional text export. The synthetic case displays 11 CV publications, 9 export entries and a 2-publication difference, while showing that one declared year does not establish the cited three-year criterion; no promotion conclusion is made.')
                    limits.append('The count and period checks are unverified text candidates from synthetic records; they do not authenticate the institution, establish publication status or determine promotion eligibility. Missing multi-year records and human institutional review remain required.')
                if name == 'PromotionProof' and PROMOTIONPROOF_PDF_ATTACHMENT_REVIEW.is_dir():
                    pdf_evidence_path = PROMOTIONPROOF_PDF_ATTACHMENT_REVIEW / 'PROMOTIONPROOF_PDF_ATTACHMENT_REVIEW_EVIDENCE.json'
                    pdf_evidence = read_json(pdf_evidence_path)
                    native_receipt_path = PROMOTIONPROOF_PDF_ATTACHMENT_REVIEW / pdf_evidence['native_route_receipt']
                    report_path = PROMOTIONPROOF_PDF_ATTACHMENT_REVIEW / pdf_evidence['reconciliation_report']
                    html_path = PROMOTIONPROOF_PDF_ATTACHMENT_REVIEW / pdf_evidence['reconciliation_html']
                    native_receipt, pdf_report = map(read_json, (native_receipt_path, report_path))
                    manifest_path = PROMOTIONPROOF_PDF_ATTACHMENT_REVIEW / 'CUSTOMER_PACKET/CUSTOMER_PACKET_MANIFEST.json'
                    manifest = read_json(manifest_path)
                    attachment_row = next((row for row in pdf_report.get('attachment_records', []) if row.get('record_id') == 'R-03'), {})
                    candidate = (attachment_row.get('count_candidates') or [{}])[0]
                    pdf_path = PROMOTIONPROOF_PDF_ATTACHMENT_REVIEW / 'CUSTOMER_PACKET/SOURCES/synthetic_institutional_export.pdf'
                    from pypdf import PdfReader
                    page_text = (PdfReader(str(pdf_path), strict=True).pages[int(candidate.get('page_number') or 1)-1].extract_text() or '')
                    start, end = int(candidate.get('page_text_char_start', -1)), int(candidate.get('page_text_char_end_exclusive', -1))
                    span = page_text[start:end] if 0 <= start <= end <= len(page_text) else ''
                    manifest_files = {str(row.get('path') or ''): row for row in manifest.get('files') or []}
                    attachment_hash = digest_file(pdf_path)
                    if (pdf_evidence.get('schema') != 'dio.promotionproof.pdf_attachment_review_execution.v1'
                            or native_receipt.get('product_name') != 'PromotionProof'
                            or native_receipt.get('packet_fingerprint') != manifest.get('packet_fingerprint')
                            or native_receipt.get('release_authorized') is not False
                            or native_receipt.get('external_effects') is not False
                            or native_receipt.get('human_review_required') is not True
                            or pdf_report.get('packet_fingerprint') != manifest.get('packet_fingerprint')
                            or attachment_row.get('source_ref') != 'customer-packet://SOURCES/synthetic_institutional_export.pdf'
                            or attachment_row.get('state') != 'PDF_TEXT_CANDIDATE_EXTRACTED'
                            or candidate.get('value') != 9 or candidate.get('verified_value') is not False
                            or candidate.get('citation_unit') != 'extracted_page_text_characters'
                            or candidate.get('source_file_sha256') != attachment_hash
                            or attachment_row.get('source_file_sha256') != attachment_hash
                            or manifest_files.get('SOURCES/synthetic_institutional_export.pdf', {}).get('sha256') != attachment_hash
                            or candidate.get('source_span_sha256') != hashlib.sha256(span.encode('utf-8')).hexdigest()
                            or span != '9'
                            or hashlib.sha256(page_text.encode('utf-8')).hexdigest() != candidate.get('page_text_sha256')
                            or digest_file(native_receipt_path) != pdf_evidence.get('native_route_receipt_sha256')
                            or digest_file(report_path) != pdf_evidence.get('reconciliation_report_sha256')
                            or digest_file(html_path) != pdf_evidence.get('reconciliation_html_sha256')
                            or pdf_evidence.get('ocr_performed') is not False
                            or pdf_evidence.get('promotion_decision_created') is not False
                            or pdf_evidence.get('external_release_authorized') is not False):
                        raise ValueError('PromotionProof PDF attachment failed manifest, page-citation, or no-decision checks')
                    product_specific_refs.extend([
                        register(pdf_evidence_path), register(native_receipt_path),
                        register(PROMOTIONPROOF_PDF_ATTACHMENT_REVIEW / 'NATIVE_ROUTE/EXECUTION/PROFESSIONAL_VAMP_PIPELINE_RECEIPT.json'),
                        register(PROMOTIONPROOF_PDF_ATTACHMENT_REVIEW / 'NATIVE_ROUTE/EXECUTION/vamp_snapshot/PRO-PROMOTIONPROOF/PRO-PROMOTIONPROOF_VAMP_EVIDENCE_SNAPSHOT.zip'),
                        register(manifest_path), register(PROMOTIONPROOF_PDF_ATTACHMENT_REVIEW / 'CUSTOMER_PACKET/SOURCES/02_evidence_register.csv'),
                        register(pdf_path), register(report_path), register(html_path),
                        register(ROOT / 'products/promotionproof_attachment_reconciliation.py'),
                    ])
                    changes.append('PromotionProof now completes a full native customer route with a manifest-bound synthetic PDF institutional export. Its page-text review extracts the declared count with page number and character offsets, then confirms the exact extracted-text span and file hash; OCR remains off.')
                    limits.append('The PDF count remains an unverified synthetic source claim; one year does not establish the three-year criterion. PDF extraction establishes neither institutional authenticity nor publication status, promotion eligibility, or a decision.')
                if name in VAMP_ATTACHMENT_DEMOS and VAMP_ATTACHMENT_DEMOS[name].is_dir():
                    demo = VAMP_ATTACHMENT_DEMOS[name]
                    demo_receipt_path = demo / f"{name.upper()}_ATTACHMENT_BINDING_DEMO_RECEIPT.json"
                    demo_receipt = read_json(demo_receipt_path)
                    projection_path = demo / 'EXECUTION/PROJECTION/VAMP_DOMAIN_PROJECTION.json'
                    projection = read_json(projection_path)
                    attachment_rows = [row for row in projection.get('rows', []) if row.get('attachment_binding')]
                    if (demo_receipt.get('status') != 'FULL_NATIVE_ROUTE_PASS_SYNTHETIC_ONLY'
                            or not attachment_rows
                            or demo_receipt.get('accepted_mappings') != 0
                            or demo_receipt.get('professional_decision') != 'not_made'
                            or demo_receipt.get('independent_signoff') != 'not_issued'):
                        raise ValueError(f'{name} attachment-bound customer execution exceeded its held-evidence boundary')
                    bindings = [row['attachment_binding'] for row in attachment_rows]
                    binding = bindings[0]
                    if any(item.get('trust_state') != 'captured_untrusted'
                           or item.get('content_validation') != 'not_performed'
                           or item.get('source_sha256') != item.get('projection_sha256')
                           or item.get('source_ref') != binding.get('source_ref')
                           for item in bindings):
                        raise ValueError(f'{name} attachment source/projection hash or trust boundary failed')
                    product_specific_refs.extend([
                        register(demo_receipt_path),
                        register(demo / 'EXECUTION/NATIVE_CUSTOMER_PACKET_RECEIPT.json'),
                        register(projection_path),
                        register(demo / 'CUSTOMER_PACKET/CUSTOMER_PACKET_MANIFEST.json'),
                        register(demo / 'CUSTOMER_PACKET/SOURCES/02_evidence_register.csv'),
                        register(demo / binding['source_ref'].replace('customer-packet://', 'CUSTOMER_PACKET/')),
                    ])
                    changes.append('A synthetic manifest-bound attachment traversed the native VAMP customer route. The original bytes and hashes are present in the review projection, with captured_untrusted status; content validation is unperformed, accepted mappings remain zero, and human professional review is required.')
                    limits.append('The attached certificate/export is synthetic and is not authenticated or substantively validated. This demonstrates provenance transport only; it does not establish CPD credit, promotion criteria, evidence sufficiency, professional interpretation or customer acceptance.')
                if name == 'Site Studio' and native_receipt.get('external_publication') != 'REFUSE':
                    raise ValueError('Site Studio customer draft is not held from publication')
                if name == 'Vesper Desk' and native_receipt.get('external_send') != 'REFUSE':
                    raise ValueError('Vesper Desk customer draft is not held from external send')
                for artifact_row in execution.get('artifacts', []):
                    relative = Path(str(artifact_row.get('path') or ''))
                    artifact_path = (customer_dir / relative).resolve()
                    if relative.is_absolute() or '..' in relative.parts or not artifact_path.is_relative_to(customer_dir.resolve()) or not artifact_path.is_file():
                        raise ValueError(f'{name} native customer artifact is missing or unsafe: {relative}')
                    register(artifact_path, artifact_row.get('sha256'))
                product_specific_refs.extend([register(package_path), register(execution_path)])
                disposition = 'CURRENT_HELD_EXECUTION_VERIFIED'
                changes.append(f"The product completed its manifest-bound native customer route, copied and rehashed its supplied packet, and generated the {package.get('terminal_artifact_kind')} for human review. Authority and external effects remained disabled.")
                limits = ['This controlled route execution uses synthetic acceptance source records and does not establish customer acceptance or source truth. Review all source-derived output, domain assumptions and unresolved exceptions before consequential use; no professional sign-off or external release is created.']
        seraph_batch_path = SOPHIA_SERAPH_PROCESS_PROOF_BATCH / 'SERAPH_PROCESS_PROOF_BATCH_RECEIPT.json'
        if name in {'Sophia Integrity', 'Sophia Research', 'Sophia Review', 'Sophia Supervisor', 'Sophia Tutor'} and seraph_batch_path.is_file():
            seraph_batch = read_json(seraph_batch_path)
            seraph_row = next((row for row in seraph_batch.get('results') or [] if row.get('product_name') == name), None)
            if (seraph_batch.get('schema') != 'dio.sophia.seraph_process_proof_batch.v1'
                    or seraph_batch.get('capture_mode') != 'RETROSPECTIVE_BOUNDED_RECONSTRUCTION_FROM_PRIOR_SOURCE_BOUND_SOPHIA_RUNS'
                    or seraph_batch.get('synthetic_acceptance_inputs_only') is not True
                    or seraph_row is None or seraph_row.get('chain_state') != 'HASH_CHAIN_VERIFIED'
                    or seraph_row.get('challenge_verdict') != 'INSUFFICIENT_EVIDENCE'
                    or seraph_row.get('signature_state') != 'UNVERIFIED'
                    or seraph_row.get('source_identity_state') != 'UNVERIFIED'
                    or seraph_row.get('delivery_released') is not False
                    or seraph_row.get('authority_created') is not False
                    or seraph_row.get('external_effects') is not False):
                raise ValueError(f'{name} Seraph process proof failed its hash-chain, reconstruction, or authority boundary')
            for relative, expected_hash in (seraph_row.get('artifacts') or {}).items():
                artifact_path = ROOT / seraph_row['proof_extension'] / 'process_proof' / relative
                if not artifact_path.is_file() or digest_file(artifact_path) != expected_hash:
                    raise ValueError(f'{name} Seraph proof artifact is missing or changed: {relative}')
                product_specific_refs.append(register(artifact_path, expected_hash))
            source_run = ROOT / seraph_row['source_native_run']
            source_receipt_path = source_run / 'EXECUTION/sophia_native' / ('PRO-' + name.casefold().replace(' ', '-').upper()) / 'SOPHIA_REVIEW_RECEIPT.json'
            source_commentary_path = source_receipt_path.with_name('REVIEWER_COMMENTARY.json')
            if (not source_receipt_path.is_file() or not source_commentary_path.is_file()
                    or digest_file(source_receipt_path) != seraph_row.get('source_receipt_sha256')
                    or digest_file(source_commentary_path) != seraph_row.get('source_commentary_sha256')):
                raise ValueError(f'{name} retrospective Seraph proof no longer binds its prior Sophia run')
            product_specific_refs.extend([register(source_receipt_path), register(source_commentary_path), register(seraph_batch_path),
                                          register(ROOT / 'products/professional_evidence_execution.py'),
                                          register(ROOT / 'products/native_customer_runner.py'),
                                          register(ROOT / 'scripts/run_sophia_seraph_process_proof_batch.py')])
            changes.append(f"Seraph verified a hash-linked process trace for the prior source-bound {name} customer run ({seraph_row.get('event_count')} event records, {seraph_row.get('audit_count')} audit records). Customer telemetry requirement was {str(seraph_row.get('seraph_telemetry_required')).lower()}; the challenge remains non-authorizing.")
            limits.append('The current Seraph trace is a retrospective reconstruction from archived Sophia receipts because the local Sophia Presence endpoint was unavailable during this refresh. Hash linkage is verified, but the trace has no trusted signer, independent collector, or authenticated clock; it does not prove model internals or review correctness.')
        live_batch_path = SOPHIA_SERAPH_LIVE_PROCESS_BATCH / 'SERAPH_LIVE_PROCESS_BATCH_RECEIPT.json'
        if name in {'Sophia Integrity', 'Sophia Research', 'Sophia Review', 'Sophia Supervisor', 'Sophia Tutor'} and live_batch_path.is_file():
            live_batch = read_json(live_batch_path)
            live_row = next((row for row in live_batch.get('results') or [] if row.get('product') == name), None)
            product_slug = name.casefold().replace(' ', '-')
            live_root = SOPHIA_SERAPH_LIVE_PROCESS_BATCH / product_slug
            proof_path = live_root / 'EXECUTION/SERAPH_PROCESSING_PROOF.json'
            trace_path = live_root / 'EXECUTION/SERAPH_PROCESSING_TRACE.json'
            challenge_path = live_root / 'EXECUTION/SERAPH_PROCESSING_CHALLENGE_RECEIPT.json'
            if (live_batch.get('schema') != 'dio.sophia.seraph_live_process_batch.v1'
                    or live_batch.get('capture_mode') != 'LIVE_SAME_PROCESS'
                    or live_batch.get('synthetic_acceptance_inputs_only') is not True
                    or live_row is None or live_row.get('status') != 'COMPLETED'
                    or not proof_path.is_file() or not trace_path.is_file() or not challenge_path.is_file()):
                raise ValueError(f'{name} live Seraph process proof is incomplete or misbound')
            live_proof = read_json(proof_path)
            live_trace = read_json(trace_path)
            live_challenge = read_json(challenge_path)
            if (live_row.get('telemetry_required') is not live_proof.get('telemetry_required_by_customer')
                    or live_proof.get('schema') != 'dio.sophia.seraph_processing_proof.v1'
                    or live_trace.get('capture_mode') != 'LIVE_SAME_PROCESS'
                    or live_proof.get('assessment_state') != 'HASH_CHAIN_VERIFIED'
                    or live_proof.get('event_count') != 3 or live_proof.get('audit_count') != 3
                    or live_proof.get('trace_sha256') != digest_file(trace_path)
                    or live_proof.get('challenge_receipt_sha256') != digest_file(challenge_path)
                    or live_challenge.get('verdict') != 'INSUFFICIENT_EVIDENCE'
                    or live_proof.get('signature_state') != 'UNVERIFIED'
                    or live_proof.get('source_identity_state') != 'UNVERIFIED'
                    or live_proof.get('delivery_released') is not False
                    or live_proof.get('constitutional_release_authorized') is not False
                    or live_proof.get('authority_created') is not False
                    or live_proof.get('external_effects') is not False):
                raise ValueError(f'{name} live Seraph trace failed integrity or held-release checks')
            product_specific_refs.extend([register(proof_path), register(trace_path), register(challenge_path),
                                          register(live_batch_path), register(live_root / 'NATIVE_CUSTOMER_PACKET_RECEIPT.json')])
            live_receipt = next(live_root.glob('EXECUTION/sophia_native/*/SOPHIA_REVIEW_RECEIPT.json'))
            live_commentary = live_receipt.with_name('REVIEWER_COMMENTARY.json')
            if (read_json(live_receipt).get('delivery_released') is not False
                    or read_json(live_receipt).get('constitutional_release_authorized') is not False):
                raise ValueError(f'{name} live Sophia route crossed its release boundary')
            product_specific_refs.extend([register(live_receipt), register(live_commentary)])
            changes.append(f"Seraph verified a live same-process route trace from the current {name} execution ({live_proof.get('event_count')} event records, {live_proof.get('audit_count')} audit records); customer telemetry was {'required' if live_proof.get('telemetry_required_by_customer') else 'optional'}. The review stayed held and the challenge remained non-authorizing.")
            limits[:] = [limit for limit in limits if not limit.startswith('The current Seraph trace is a retrospective reconstruction from archived Sophia receipts')]
            limits.append('The live process proof covers five synthetic acceptance runs only. Its hash chain is unsigned and has no trusted clock or independent collector; it does not prove model internals, customer acceptance, academic source truth, or review correctness.')
        if name == 'Accessible Publish' and ACCESSIBLE_PUBLISH_CUSTOMER_DEMO.is_dir():
            receipt_path = ACCESSIBLE_PUBLISH_CUSTOMER_DEMO / 'ACCESSIBLE_PUBLISH_RECEIPT.json'
            execution_path = ACCESSIBLE_PUBLISH_CUSTOMER_DEMO / 'CUSTOMER_EXECUTION_RECEIPT.json'
            if not receipt_path.is_file() or not execution_path.is_file():
                raise ValueError('Accessible Publish customer execution receipt is missing')
            accessible = read_json(receipt_path)
            if accessible.get('release_authorized') is not False or accessible.get('conformance_claim') != 'NONE' or accessible.get('external_effects') is not False:
                raise ValueError('Accessible Publish execution exceeded its held review boundaries')
            for artifact_row in accessible.get('artifacts', []):
                product_specific_refs.append(register(ACCESSIBLE_PUBLISH_CUSTOMER_DEMO / artifact_row['path'], artifact_row.get('sha256')))
            product_specific_refs.extend([register(receipt_path), register(execution_path)])
            disposition = 'CURRENT_HELD_EXECUTION_VERIFIED'
            changes.append('A source packet was executed through the catalog customer route, producing a source-preserving prepared HTML, static findings and owner remediation checklist. The controlled example is explicitly synthetic and remains held for accessibility review.')
            limits = ['The route checks a limited static subset of WCAG 2.2 signals. The synthetic example does not establish customer acceptance, conformance, PDF/UA, browser behavior, contrast or assistive-technology usability; owner and accessibility review remain required.']
        if name == 'Accessible Publish' and ACCESSIBLE_PUBLISH_SEMANTICS_DEMO.is_dir():
            evidence_path = ACCESSIBLE_PUBLISH_SEMANTICS_DEMO / 'SEMANTIC_INVENTORY_EXECUTION_EVIDENCE.json'
            receipt_path = ACCESSIBLE_PUBLISH_SEMANTICS_DEMO / 'ACCESSIBLE_PUBLISH_RECEIPT.json'
            execution_path = ACCESSIBLE_PUBLISH_SEMANTICS_DEMO / 'CUSTOMER_EXECUTION_RECEIPT.json'
            review_path = ACCESSIBLE_PUBLISH_SEMANTICS_DEMO / 'ACCESSIBILITY_REVIEW.json'
            evidence, accessible, execution, review = map(read_json, (evidence_path, receipt_path, execution_path, review_path))
            if (evidence.get('schema') != 'dio.accessible_publish.semantic_inventory_execution.v1'
                    or evidence.get('implicit_label_recognized') is not True
                    or evidence.get('valid_aria_labelledby_recognized') is not True
                    or evidence.get('broken_aria_labelledby_flagged') is not True
                    or evidence.get('empty_link_flagged') is not True
                    or evidence.get('duplicate_ids_flagged') is not True
                    or evidence.get('focusable_descendant_of_aria_hidden_flagged') is not True
                    or evidence.get('form_controls_detected') != 4
                    or evidence.get('hidden_controls_excluded') != 1
                    or evidence.get('empty_text_aria_labelledby_flagged') is not True
                    or evidence.get('accessible_name_algorithm_claim') != 'NONE_STATIC_DESCENDANT_TEXT_PROXY_ONLY'
                    or accessible.get('release_authorized') is not False
                    or accessible.get('conformance_claim') != 'NONE'
                    or execution.get('release_authorized') is not False
                    or execution.get('external_effects') is not False
                    or review.get('conformance_claim') != 'NONE'):
                raise ValueError('Accessible Publish semantic inventory result failed held-review or detector evidence checks')
            product_specific_refs.extend([register(evidence_path), register(receipt_path), register(execution_path), register(review_path)])
            for artifact_row in accessible.get('artifacts', []):
                product_specific_refs.append(register(ACCESSIBLE_PUBLISH_SEMANTICS_DEMO / artifact_row['path'], artifact_row.get('sha256')))
            disposition = 'CURRENT_HELD_EXECUTION_VERIFIED'
            changes.append('Accessible Publish recognizes nested label semantics, excludes hidden inputs, flags missing and empty-text aria-labelledby targets, unnamed links and duplicate IDs, and detects focusable controls inside aria-hidden regions. The empty-target check is explicitly a static text proxy, not a complete accessible-name computation; publication remains held.')
            limits = ['Static semantic checks flag keyboard-reachable controls hidden from the accessibility tree. The full review still does not establish complete keyboard operation, screen-reader behavior, PDF/UA, or WCAG conformance; owner and accessibility review remain required.']
        if name == 'Accessible Publish' and ACCESSIBLE_PUBLISH_RENDERED_DEMO.is_dir():
            evidence_path = ACCESSIBLE_PUBLISH_RENDERED_DEMO / 'RENDERED_ACCESSIBILITY_EXECUTION_EVIDENCE.json'
            receipt_path = ACCESSIBLE_PUBLISH_RENDERED_DEMO / 'ACCESSIBLE_PUBLISH_RECEIPT.json'
            execution_path = ACCESSIBLE_PUBLISH_RENDERED_DEMO / 'CUSTOMER_EXECUTION_RECEIPT.json'
            review_path = ACCESSIBLE_PUBLISH_RENDERED_DEMO / 'ACCESSIBILITY_REVIEW.json'
            rendered_path = ACCESSIBLE_PUBLISH_RENDERED_DEMO / 'RENDERED_ACCESSIBILITY_REVIEW.json'
            evidence, accessible, execution, review, rendered = map(read_json, (evidence_path, receipt_path, execution_path, review_path, rendered_path))
            if (evidence.get('schema') != 'dio.accessible_publish.rendered_execution_evidence.v2'
                    or evidence.get('runtime_state') != 'STATIC_AND_SCRIPTED_DOM_NETWORK_BLOCKED'
                    or evidence.get('network_blocked') is not True or evidence.get('scripts_disabled') is not False
                    or evidence.get('script_execution_isolated') is not True or evidence.get('script_network_blocked') is not True
                    or evidence.get('script_generated_focusable_delta', 0) < 1
                    or evidence.get('contrast_failure_count', 0) < 1 or evidence.get('focus_failure_count', 0) < 1
                    or evidence.get('viewport_count') != 4 or evidence.get('horizontal_overflow_viewport_count') is None
                    or rendered.get('source_sha256') != review.get('prepared_html_sha256')
                    or accessible.get('release_authorized') is not False
                    or accessible.get('conformance_claim') != 'NONE'
                    or execution.get('release_authorized') is not False
                    or execution.get('external_effects') is not False):
                raise ValueError('Accessible Publish rendered review failed its deliberate-issue, source-binding or held-release checks')
            product_specific_refs.extend([register(evidence_path), register(receipt_path), register(execution_path), register(review_path), register(rendered_path)])
            for artifact_row in accessible.get('artifacts', []):
                product_specific_refs.append(register(ACCESSIBLE_PUBLISH_RENDERED_DEMO / artifact_row['path'], artifact_row.get('sha256')))
            disposition = 'CURRENT_HELD_EXECUTION_VERIFIED'
            changes.append('The controlled HTML case receives static and bounded post-load Chromium review at 320, 375, 768 and 1280 CSS pixels. A disposable process executes inline scripts with all requests blocked, then inspects generated focusable controls, tab focus, hidden focusables, viewport width and page errors. The deliberate static contrast/focus issues and script-generated control were detected; publication remains held.')
            limits = ['The script review covers a 200 ms post-load observation, programmatic tab traversal and a bounded set of visible type="button" interactions. It does not cover links, form submission, custom controls, full user journeys, screen-reader output, PDF/UA, all contrast/background compositions or full WCAG conformance; owner and accessibility review remain required.']
        if name == 'Accessible Publish' and ACCESSIBLE_PUBLISH_LIVE_BROWSER_DEMO.is_dir():
            evidence_path = ACCESSIBLE_PUBLISH_LIVE_BROWSER_DEMO / 'RENDERED_ACCESSIBILITY_EXECUTION_EVIDENCE.json'
            receipt_path = ACCESSIBLE_PUBLISH_LIVE_BROWSER_DEMO / 'ACCESSIBLE_PUBLISH_RECEIPT.json'
            execution_path = ACCESSIBLE_PUBLISH_LIVE_BROWSER_DEMO / 'CUSTOMER_EXECUTION_RECEIPT.json'
            review_path = ACCESSIBLE_PUBLISH_LIVE_BROWSER_DEMO / 'ACCESSIBILITY_REVIEW.json'
            rendered_path = ACCESSIBLE_PUBLISH_LIVE_BROWSER_DEMO / 'RENDERED_ACCESSIBILITY_REVIEW.json'
            evidence, accessible, execution, review, rendered = map(read_json, (evidence_path, receipt_path, execution_path, review_path, rendered_path))
            rendered_review = review.get('rendered_browser_review') or {}
            if (evidence.get('schema') != 'dio.accessible_publish.rendered_execution_evidence.v2'
                    or evidence.get('controlled_synthetic_demo') is not True
                    or evidence.get('runtime_state') != 'STATIC_AND_SCRIPTED_DOM_NETWORK_BLOCKED'
                    or evidence.get('scripted_runtime_state') != 'SCRIPTED_POSTLOAD_DOM_INSPECTED'
                    or evidence.get('script_execution_isolated') is not True
                    or evidence.get('script_network_blocked') is not True
                    or evidence.get('viewport_count') != 4
                    or evidence.get('horizontal_overflow_viewport_count') != 0
                    or evidence.get('contrast_failure_count', 0) < 1
                    or evidence.get('focus_failure_count', 0) < 1
                    or evidence.get('script_generated_focusable_delta', 0) < 1
                    or evidence.get('review_sha256') != digest_file(review_path)
                    or evidence.get('rendered_review_sha256') != digest_file(rendered_path)
                    or rendered.get('source_sha256') != review.get('prepared_html_sha256')
                    or rendered_review.get('runtime_state') != evidence.get('runtime_state')
                    or accessible.get('release_authorized') is not False
                    or accessible.get('conformance_claim') != 'NONE'
                    or execution.get('release_authorized') is not False
                    or execution.get('external_effects') is not False):
                raise ValueError('Accessible Publish latest browser review failed its source, runtime, or held-release checks')
            product_specific_refs.extend([register(evidence_path), register(receipt_path), register(execution_path), register(review_path), register(rendered_path)])
            for artifact_row in accessible.get('artifacts', []):
                product_specific_refs.append(register(ACCESSIBLE_PUBLISH_LIVE_BROWSER_DEMO / artifact_row['path'], artifact_row.get('sha256')))
            disposition = 'CURRENT_HELD_EXECUTION_VERIFIED'
            changes.append('The current customer route completed isolated static and scripted Chromium review at 320, 375, 768 and 1280 CSS pixels. It reproduced low contrast and missing keyboard focus, detected a script-generated control, and found no horizontal overflow in this controlled fixture. The source-bound report and owner remediation checklist remain held for review.')
            limits = ['This is a controlled synthetic page, not a customer-site acceptance. The bounded browser pass does not establish complete keyboard or screen-reader usability, PDF/UA, destination/server behavior, all dynamic journeys, full WCAG conformance or publication authority; owner and accessibility review remain required.']
        if name == 'Accessible Publish' and ACCESSIBLE_PUBLISH_CUSTOMER_REVIEW_BUNDLE.is_dir():
            manifest_path = ACCESSIBLE_PUBLISH_CUSTOMER_REVIEW_BUNDLE / 'BUNDLE_MANIFEST.json'
            manifest = read_json(manifest_path)
            archive_path = ACCESSIBLE_PUBLISH_CUSTOMER_REVIEW_BUNDLE.with_suffix('.zip')
            if (manifest.get('schema') != 'dio.accessible_publish.customer_review_bundle.v1'
                    or manifest.get('release_authorized') is not False
                    or manifest.get('external_publication') is not False
                    or manifest.get('conformance_claim') != 'NONE'
                    or not (ACCESSIBLE_PUBLISH_CUSTOMER_REVIEW_BUNDLE / 'index.html').is_file()
                    or not archive_path.is_file()):
                raise ValueError('Accessible Publish customer bundle failed its held-review or packaging checks')
            for item in manifest.get('files', []):
                path = ACCESSIBLE_PUBLISH_CUSTOMER_REVIEW_BUNDLE / item['path']
                if (not path.is_file() or path.stat().st_size != item.get('bytes')
                        or digest_file(path) != item.get('sha256')):
                    raise ValueError(f'Accessible Publish review bundle hash/size mismatch: {item.get("path")}')
                product_specific_refs.append(register(path, item['sha256']))
            with zipfile.ZipFile(archive_path) as archive:
                archived_names = set(archive.namelist())
                expected_names = {path.name for path in ACCESSIBLE_PUBLISH_CUSTOMER_REVIEW_BUNDLE.iterdir() if path.is_file()}
                if archived_names != expected_names:
                    raise ValueError('Accessible Publish review bundle archive member set differs from its directory')
                for item in manifest.get('files', []):
                    if hashlib.sha256(archive.read(item['path'])).hexdigest() != item['sha256']:
                        raise ValueError(f'Accessible Publish review bundle archive hash mismatch: {item["path"]}')
            product_specific_refs.extend([register(manifest_path), register(archive_path, digest_file(archive_path)),
                                          register(ROOT / 'scripts/build_accessible_publish_customer_review_bundle.py')])
            changes.append('The held browser review now has a navigable offline customer package that brings the synthetic source, static and rendered findings, owner remediation checklist, execution evidence and explicit review limits together. The package and archive are hash bound; neither creates publication authority or a conformance claim.')
            limits.append('The customer bundle organizes existing controlled synthetic review evidence; it does not add independent accessibility testing, owner responses, customer-site validation or conformance evidence.')
        if name == 'Accessible Publish' and ACCESSIBLE_PUBLISH_INTERACTION_DEMO.is_dir():
            evidence_path = ACCESSIBLE_PUBLISH_INTERACTION_DEMO / 'INTERACTION_EXECUTION_EVIDENCE.json'
            receipt_path = ACCESSIBLE_PUBLISH_INTERACTION_DEMO / 'ACCESSIBLE_PUBLISH_RECEIPT.json'
            execution_path = ACCESSIBLE_PUBLISH_INTERACTION_DEMO / 'CUSTOMER_EXECUTION_RECEIPT.json'
            review_path = ACCESSIBLE_PUBLISH_INTERACTION_DEMO / 'ACCESSIBILITY_REVIEW.json'
            evidence, accessible, execution, review = map(read_json, (evidence_path, receipt_path, execution_path, review_path))
            rendered = review.get('rendered_browser_review') or {}
            if (evidence.get('schema') != 'dio.accessible_publish.interaction_execution_evidence.v1'
                    or evidence.get('controlled_synthetic_demo') is not True
                    or evidence.get('button_interaction_count', 0) < 1
                    or evidence.get('controlled_content_visible_after_activation') is not True
                    or evidence.get('network_blocked') is not True
                    or rendered.get('scripted_button_interaction_count', 0) < 1
                    or not any(row.get('controlled_content_visible') is True for row in rendered.get('scripted_button_interaction_reviews', []))
                    or accessible.get('release_authorized') is not False
                    or accessible.get('conformance_claim') != 'NONE'
                    or execution.get('release_authorized') is not False
                    or execution.get('external_effects') is not False):
                raise ValueError('Accessible Publish interaction result failed its controlled disclosure or held-release checks')
            product_specific_refs.extend([register(evidence_path), register(receipt_path), register(execution_path), register(review_path)])
            for artifact_row in accessible.get('artifacts', []):
                product_specific_refs.append(register(ACCESSIBLE_PUBLISH_INTERACTION_DEMO / artifact_row['path'], artifact_row.get('sha256')))
            disposition = 'CURRENT_HELD_EXECUTION_VERIFIED'
            changes.append('A new isolated browser pass activates visible non-submit buttons in a network-blocked disposable page and records changes to text, aria-expanded/pressed state and aria-controls content visibility. A synthetic disclosure was detected at all four viewports; publication remains held.')
            limits = ['Interaction checks are bounded to at most 10 visible type="button" controls per viewport in a synthetic demonstration. Links, form submission, custom controls and complete user journeys remain unreviewed; screen-reader output, PDF/UA, full WCAG conformance and customer acceptance are unverified.']
        if name == 'Accessible Publish' and ACCESSIBLE_PUBLISH_LINK_FORM_DEMO.is_dir():
            evidence_path = ACCESSIBLE_PUBLISH_LINK_FORM_DEMO.parent / 'ACCESSIBLE_PUBLISH_LINK_FORM_DEMO_20261102_V1.json'
            receipt_path = ACCESSIBLE_PUBLISH_LINK_FORM_DEMO / 'ACCESSIBLE_PUBLISH_RECEIPT.json'
            execution_path = ACCESSIBLE_PUBLISH_LINK_FORM_DEMO / 'CUSTOMER_EXECUTION_RECEIPT.json'
            review_path = ACCESSIBLE_PUBLISH_LINK_FORM_DEMO / 'ACCESSIBILITY_REVIEW.json'
            evidence, receipt, execution, review = map(read_json, (evidence_path, receipt_path, execution_path, review_path))
            rendered = review.get('rendered_browser_review') or {}
            if (evidence.get('schema') != 'dio.accessible_publish.link_form_execution_evidence.v1'
                    or evidence.get('scripted_runtime_state') != 'SCRIPTED_POSTLOAD_DOM_INSPECTED'
                    or evidence.get('link_interaction_count') != 8
                    or evidence.get('form_submission_attempt_count') != 4
                    or evidence.get('navigation_and_submission_blocked') is not True
                    or evidence.get('page_error_count') != 0
                    or rendered.get('native_link_navigation_blocked') is not True
                    or rendered.get('native_form_submission_blocked') is not True
                    or receipt.get('release_authorized') is not False
                    or receipt.get('external_publication') is not False
                    or receipt.get('conformance_claim') != 'NONE'
                    or execution.get('external_effects') is not False):
                raise ValueError('Accessible Publish link/form exercise did not preserve the isolated held-review boundary')
            product_specific_refs.extend([register(evidence_path), register(receipt_path), register(execution_path), register(review_path),
                                          register(ROOT / 'scripts/run_accessible_publish_link_form_demo.py')])
            for artifact_row in execution.get('artifacts', []):
                product_specific_refs.append(register(ACCESSIBLE_PUBLISH_LINK_FORM_DEMO / artifact_row['path'], artifact_row.get('sha256')))
            disposition = 'CURRENT_HELD_EXECUTION_VERIFIED'
            changes.append('The isolated browser review now activates a bounded sample of links and submits forms with server navigation and native submission blocked. It records link behavior, HTML validity and page submit-handler cancellation without exporting raw target URLs or form actions; publication remains held.')
            limits = ['This synthetic browser pass covers at most ten links and ten forms per viewport. It does not verify destination correctness, server-side responses, custom widgets, full journeys, screen-reader behavior, PDF/UA, WCAG conformance or customer acceptance.']
        if name == 'Accessible Publish' and ACCESSIBLE_PUBLISH_LIVE_BROWSER_DEMO.is_dir():
            changes.append('A newer source-bound browser artifact confirms the current route detects fixture contrast and focus defects across four viewports, detects a script-generated control, and records zero horizontal overflow for that fixture. It complements the link/form interaction pass; both remain synthetic and non-authorizing.')
            limits.append('The four-viewport contrast/focus observation is from a deliberately defective synthetic fixture; it is detector evidence, not a customer-site result or an accessibility pass.')
        if name == 'Contract Desk' and contract_lineage_validation.is_file() and contract_case_receipt.is_file():
            worksheet_receipt = read_json(contract_worksheet_receipt) if contract_worksheet_receipt.is_file() else {}
            worksheet = read_json(contract_worksheet) if contract_worksheet.is_file() else {}
            worksheet_items = worksheet.get('items') or []
            date_receipt = read_json(contract_date_receipt) if contract_date_receipt.is_file() else {}
            date_scenario_bundle = read_json(contract_date_scenarios) if contract_date_scenarios.is_file() else {}
            date_scenarios = date_scenario_bundle.get('scenarios') or []
            if (worksheet_receipt.get('review_worksheet_artifact') != 'REVIEW_WORKSHEET.csv'
                    or worksheet_receipt.get('review_worksheet_items') != len(worksheet_items)
                    or worksheet.get('schema') != 'dio.contract_desk.review_worksheet.v1'
                    or worksheet.get('claim_boundary') != 'Reviewer handoff only. Blank fields require customer completion. Conditional weekday-only date scenarios are separate and do not provide legal interpretation or certified deadlines.'
                    or any(any(item.get(field) for field in ('reviewer_response', 'assigned_owner', 'follow_up_date', 'owner_disposition'))
                           for item in worksheet_items)
                    or date_receipt.get('status') != 'HELD_REVIEW_PACKAGE_RENDERED'
                    or date_receipt.get('professional_approval') != 'NOT_GRANTED'
                    or date_receipt.get('legal_interpretation_or_lateness_finding') != 'NOT_MADE'
                    or len(date_scenarios) != 1
                    or date_scenarios[0].get('candidate_due_date') != '2026-08-07'
                    or date_scenarios[0].get('recorded_event_date') != '2026-08-08'
                    or date_scenarios[0].get('candidate_status') != 'CONDITIONAL_REVIEW_ONLY'
                    or date_scenarios[0].get('counting_convention_assumed') != 'Month-end is excluded; counting starts on the next calendar day; Monday-Friday count as business days; the candidate date is the final counted day.'
                    or [(step.get('date'), step.get('treatment'), step.get('business_day_number')) for step in date_scenarios[0].get('calendar_steps', [])] != [
                        ('2026-08-01', 'WEEKEND_EXCLUDED', None), ('2026-08-02', 'WEEKEND_EXCLUDED', None),
                        ('2026-08-03', 'COUNTED_BUSINESS_DAY', 1), ('2026-08-04', 'COUNTED_BUSINESS_DAY', 2),
                        ('2026-08-05', 'COUNTED_BUSINESS_DAY', 3), ('2026-08-06', 'COUNTED_BUSINESS_DAY', 4),
                        ('2026-08-07', 'COUNTED_BUSINESS_DAY', 5)]
                    or len(date_scenarios[0].get('review_questions') or []) < 4
                    or len(date_scenarios[0].get('source_bindings') or []) != 2):
                raise ValueError('Contract Desk review worksheet or conditional calendar trace is stale, incomplete or contains prefilled owner decisions')
            product_specific_refs.extend([
                register(contract_case_receipt), register(contract_lineage_validation),
                register(contract_lineage_root / 'EXECUTION/contract_desk/SOURCE_LINEAGE.json'),
                register(contract_lineage_root / 'EXECUTION/contract_desk/OBLIGATION_BUNDLE.json'),
                register(contract_lineage_root / 'EXECUTION/contract_desk/CUSTOMER_PACKAGE_RECEIPT.json'),
                register(contract_worksheet_receipt), register(contract_worksheet),
                register(contract_worksheet_root / 'REVIEW_WORKSHEET.csv'),
                register(contract_worksheet_root / 'SOURCE_LINEAGE.json'),
                register(contract_date_scenarios), register(contract_date_receipt),
                register(contract_date_scenario_root / 'CUSTOMER_PACKAGE_RECEIPT.json'),
                register(contract_date_scenario_root / 'REVIEW_CONTENT.json'),
            ])
            changes.append(f'The current customer route validates every clause byte span against the original packet, binds extracted obligation candidates to exact source-clause text and hashes, provides an editable owner handoff worksheet for {len(worksheet_items)} unresolved questions, and shows the date-by-date Monday-Friday count behind the conditional 7 August candidate, including excluded weekend days and trigger/deadline assumptions to confirm.')
            limits = ['Exact source linkage and weekday arithmetic are verified. The agreement does not define business day or jurisdiction/holiday treatment; the candidate date is not certified, and lateness, breach, legal significance, statement truth, applicability and professional approval remain unestablished.']
        if name == 'Article Publication' and article_publication_binding_receipt.is_file() and article_publication_case_receipt.is_file():
            product_specific_refs.extend([
                register(article_publication_case_receipt), register(article_publication_bindings),
                register(article_publication_editor_bindings), register(article_publication_binding_receipt),
                register(article_publication_execution / 'composition/PROOF_MANIFEST.json'),
                register(article_publication_execution / 'composition/publication/ARTICLE_LINEAGE_OBJECT.json'),
            ])
            article_claims = read_json(article_publication_bindings).get('claims') or []
            changes.append(f"The Article Publication route binds all {len(article_claims)} draft claims to exact evidence-register rows with verified UTF-8 byte spans, row/file hashes and native proof linkage; truth, rights and editorial review remain pending.")
            limits = ['Exact source lineage identifies the customer assertions used, but does not verify truth, rights, attribution, factual accuracy or suitability for publication.']
        if name == 'Finance Readiness' and finance_binding_validation.is_file() and finance_binding_case_receipt.is_file():
            product_specific_refs.extend([
                register(finance_binding_case_receipt), register(finance_binding_validation),
                register(finance_binding_root / 'EXECUTION/finance_readiness/SOURCE_BINDINGS.json'),
                register(finance_binding_root / 'EXECUTION/finance_readiness/READINESS_EVIDENCE_MATRIX.json'),
                register(finance_binding_root / 'EXECUTION/finance_readiness/CUSTOMER_PACKAGE_RECEIPT.json'),
            ])
            finance_validation = read_json(finance_binding_validation)
            changes.append(f"The customer route verifies {finance_validation.get('verified_customer_record_anchor_count')} cited customer records against exact evidence-register bytes and row hashes. The assertions and any finance or lender conclusions remain unverified.")
            limits = ['Byte-bound record identity is verified. Customer statement truth, source currency, financial conclusions, lender applicability/eligibility and professional approval remain unestablished.']
        if name == 'Finance Readiness Studio' and finance_studio_validation.is_file() and finance_studio_case_receipt.is_file():
            product_specific_refs.extend([
                register(finance_studio_case_receipt), register(finance_studio_validation),
                register(finance_studio_validation_root / 'EXECUTION/FINANCE_READINESS_STUDIO_SOURCE_BINDINGS.json'),
                register(finance_studio_validation_root / 'EXECUTION/FINANCE_READINESS_STUDIO_SOURCE_BINDINGS_RECEIPT.json'),
                register(finance_studio_validation_root / 'EXECUTION/finance_readiness_studio/composition/finance/FINANCE_READINESS_OBJECT.json'),
            ])
            studio_validation = read_json(finance_studio_validation)
            amount_check = studio_validation['amount_reconciliation']
            changes.append(f"The Studio route verifies {studio_validation['verified_record_count']} source-register rows against exact bytes and recomputes the customer-stated funding/use variance as {amount_check['arithmetic_variance']}; lender and affordability decisions remain unmade.")
            limits = ['The route verifies source-row identity and arithmetic over customer assertions only. It does not authenticate records, establish lender requirements, determine affordability or make a financing decision.']
        if name == 'Finance Readiness Studio' and finance_studio_amount_spans.is_file():
            product_specific_refs.append(register(finance_studio_amount_spans))
            amount_span_doc = read_json(finance_studio_amount_spans)
            changes.append(f"The Studio now binds each of its {len(amount_span_doc.get('bindings') or [])} arithmetic inputs to exact register-byte spans with phrase, row and file hashes; these identifiers do not verify the customer's assertions.")
        if name == 'Finance Readiness Studio' and finance_currency_evidence.is_file():
            product_specific_refs.append(register(finance_currency_evidence))
            changes.append('The currency-handling route recognizes explicit ISO codes, normalizes R to ZAR, and holds mixed-currency inputs without calculating a total or variance.')
        if name == 'Report & Pitch Studio' and report_pitch_bindings.is_file() and report_pitch_case_receipt.is_file():
            report_pitch_review_page = report_pitch_lineage_root / 'EXECUTION/report_pitch_studio/EDITORIAL_REVIEW.html'
            report_pitch_review_validation = report_pitch_lineage_root / 'EXECUTION/report_pitch_studio/EDITORIAL_REVIEW_VALIDATION.json'
            report_pitch_package_manifest = report_pitch_lineage_root / 'EXECUTION/report_pitch_studio/package_manifest.json'
            pitch_validation_receipt = read_json(report_pitch_review_validation)
            pitch_manifest = read_json(report_pitch_package_manifest)
            review_evidence = read_json(report_pitch_review_evidence)
            layout_case_root = report_pitch_visual_review.parent
            layout_review = read_json(report_pitch_visual_review) if report_pitch_visual_review.is_file() else {}
            layout_manifest_path = layout_case_root / 'package_manifest.json'
            layout_manifest = read_json(layout_manifest_path) if layout_manifest_path.is_file() else {}
            layout_archive_path = layout_case_root / 'controlled_review_package.zip'
            pitch_manifest_artifacts = {row.get('path'): row.get('sha256') for row in pitch_manifest.get('artifacts') or []}
            if (not report_pitch_review_page.is_file()
                    or review_evidence.get('schema') != 'dio.report_pitch.editorial_review_surface_evidence.v1'
                    or review_evidence.get('review_page_sha256') != hashlib.sha256(report_pitch_review_page.read_bytes()).hexdigest()
                    or review_evidence.get('validation_sha256') != hashlib.sha256(report_pitch_review_validation.read_bytes()).hexdigest()
                    or not all((review_evidence.get('checks') or {}).values())
                    or pitch_manifest_artifacts.get('EDITORIAL_REVIEW.html') != hashlib.sha256(report_pitch_review_page.read_bytes()).hexdigest()
                    or pitch_manifest_artifacts.get('EDITORIAL_REVIEW_VALIDATION.json') != hashlib.sha256(report_pitch_review_validation.read_bytes()).hexdigest()
                    or pitch_validation_receipt.get('state') != 'REVIEW_INCOMPLETE_OR_HOLD_REQUIRED'
                    or pitch_validation_receipt.get('publication_authorized') is not False
                    or layout_review.get('result') != 'PASS_LAYOUT_ONLY'
                    or len([row for row in layout_review.get('artifacts', []) if Path(row.get('path', '')).name.startswith('slide-')]) != 7
                    or layout_manifest.get('qa', {}).get('visual_review') != 'PASS_LAYOUT_ONLY'
                    or layout_manifest.get('post_render_visual_review', {}).get('review_sha256') != hashlib.sha256(report_pitch_visual_review.read_bytes()).hexdigest()
                    or not layout_archive_path.is_file()):
                raise ValueError('Report & Pitch guided editorial review did not retain package hashes and a held release boundary')
            with zipfile.ZipFile(layout_archive_path) as archive:
                archive_manifest = json.loads(archive.read('package_manifest.json'))
                archive_review = json.loads(archive.read('REPORT_PITCH_VISUAL_REVIEW.json'))
                if (archive_manifest.get('qa', {}).get('visual_review') != 'PASS_LAYOUT_ONLY'
                        or archive_review.get('result') != 'PASS_LAYOUT_ONLY'):
                    raise ValueError('Report & Pitch archived package does not include its passing layout review')
            product_specific_refs.extend([
                register(report_pitch_case_receipt), register(report_pitch_bindings), register(report_pitch_bindings_receipt),
                register(report_pitch_review_evidence),
                register(report_pitch_lineage_root / 'EXECUTION/report_pitch_studio/EDITORIAL_REVIEW_WORKSHEET.csv'),
                register(report_pitch_review_page), register(report_pitch_review_validation),
                register(report_pitch_package_manifest), register(report_pitch_lineage_root / 'EXECUTION/report_pitch_studio/controlled_review_package.zip'),
                register(ROOT / 'products/report_pitch_editorial_review.py'),
                register(ROOT / 'products/report_pitch_pipeline.py'),
                register(ROOT / 'scripts/validate_report_pitch_editorial_review.py'),
                register(ROOT / 'scripts/run_report_pitch_editorial_review_surface.py'),
                register(report_pitch_visual_review), register(layout_manifest_path), register(layout_archive_path),
                register(ROOT / 'scripts/finalize_report_pitch_visual_review.py'),
            ])
            pitch_validation = read_json(report_pitch_bindings_receipt)
            changes.append(f"The route now byte-binds all {pitch_validation.get('binding_count')} customer-source claims to exact evidence-register rows across its report, pitch and article review package; factual, rights and editorial approval remain pending.")
            changes.append('Report & Pitch Studio now provides an offline claim-by-claim review workspace with direct report, article and pitch links, immutable source fields, decision controls, reviewer CSV export and a source-field validator. Review completion never grants publication authority.')
            changes.append('The customer package now carries the completed seven-slide layout review in both its manifest and downloadable archive; the review is limited to layout and does not imply claim truth, expert approval, rights clearance, or publication authority.')
            limits = ['Byte-accurate source lineage identifies the customer statements used but does not verify truth, source authenticity, rights, editorial quality or publication suitability.']
        if name == 'InvestorProof' and investorproof_validation.is_file() and investorproof_case_receipt.is_file():
            product_specific_refs.extend([
                register(investorproof_case_receipt), register(investorproof_validation),
                register(investorproof_root / 'EXECUTION/investorproof/FINANCIAL_REVIEW_WORKBOOK.xlsx'),
                register(investorproof_root / 'EXECUTION/investorproof/FINANCIAL_SOURCE_BINDINGS.json'),
                register(investorproof_root / 'EXECUTION/investorproof/CUSTOMER_PACKAGE_RECEIPT.json'),
            ])
            investor_validation = read_json(investorproof_validation)
            changes.append(f"InvestorProof now verifies all {investor_validation.get('verified_amount_count')} extracted FY2025 measures against the original evidence-register rows, recomputes its ratios/runway, and confirms the delivered workbook matches; the customer accounts and investor conclusions remain unverified.")
            limits = ['This check validates amount extraction, arithmetic and workbook consistency only. The supplied accounts are unaudited customer assertions; no audit opinion, valuation, investor suitability or funding approval is produced.']
        if name == 'VAMP Performance' and vamp_window_binding.is_file() and vamp_window_case_receipt.is_file():
            product_specific_refs.extend([register(vamp_window_case_receipt), register(vamp_window_binding)])
            scope_binding = read_json(vamp_window_binding).get('review_window_source_binding') or {}
            changes.append(f"The review window is now bound to evidence-register record {scope_binding.get('record_id')} with exact source-file, row and statement hashes and byte offsets; objective achievement and event dates still require review.")
            limits = ['The declared review period and snapshot row/window consistency are byte-bound. Event dates, evidence authenticity, objective sufficiency and achievement remain unverified; no employee rating or promotion/CPD decision is made.']
        if name == 'DIO RegOps' and regops_review_pack.is_file() and regops_review_receipt.is_file():
            regops_pack = read_json(regops_review_pack)
            regops_receipt = read_json(regops_review_receipt)
            customer_rows = regops_pack.get('customer_statement_review_register') or []
            raw_source = regops_review_source.read_bytes()
            source_digest = hashlib.sha256(raw_source).hexdigest()
            exact_rows = []
            for item in customer_rows:
                start, end = int(item.get('source_byte_start', -1)), int(item.get('source_byte_end_exclusive', -1))
                source_row = raw_source[start:end] if start >= 0 and end >= start else b''
                exact_rows.append(bool(source_row) and hashlib.sha256(source_row).hexdigest() == item.get('source_row_sha256')
                                  and item.get('source_file_sha256') == source_digest
                                  and hashlib.sha256(str(item.get('customer_statement') or '').encode('utf-8')).hexdigest() == item.get('source_statement_sha256'))
            source_refs = {row.get('source_ref') for row in customer_rows}
            evidence_refs = {row.get('source_ref') for row in regops_pack.get('evidence_receipt_set') or []}
            record_kinds = {row.get('record_kind') for row in customer_rows}
            deadline_row = next((row for row in customer_rows if row.get('record_id') == 'R-01'), {})
            review_date = regops_pack.get('customer_statement_review_as_of_date')
            processing_receipt = read_json(regops_processing_receipt)
            processed_at = str(processing_receipt.get('processed_at') or '')
            processed_date = datetime.fromisoformat(processed_at.replace('Z', '+00:00')).date().isoformat()
            if (regops_receipt.get('status') != 'PASS_FULL_PIPELINE'
                    or processing_receipt.get('readiness_state') != 'REFUSE'
                    or processing_receipt.get('external_release_gate') != 'REFUSE'
                    or processing_receipt.get('authority_created') is not False
                    or regops_pack.get('readiness_decision', {}).get('state') != 'REFUSE'
                    or len(customer_rows) != 4 or not exact_rows or not all(exact_rows)
                    or source_refs != evidence_refs
                    or not review_date or review_date != processed_date
                    or deadline_row.get('date_candidate_timing_state') != 'CUSTOMER_STATED_DATE_PAST_AS_OF_REVIEW_DATE_UNVERIFIED'
                    or not deadline_row.get('customer_stated_date_candidate')
                    or deadline_row.get('customer_stated_date_candidate') >= review_date
                    or deadline_row.get('review_as_of_date') != review_date
                    or 'submission receipt' not in str(deadline_row.get('requested_follow_up') or '').casefold()
                    or 'extension' not in str(deadline_row.get('requested_follow_up') or '').casefold()
                    or 'does not establish' not in str(deadline_row.get('requested_follow_up') or '').casefold()
                    or any(row.get('review_as_of_date') != review_date for row in customer_rows)
                    or record_kinds != {'CUSTOMER_STATED_DEADLINE', 'CUSTOMER_STATED_OWNER_ROLE', 'CUSTOMER_REPORTED_POLICY_REVIEW_EVENT', 'CUSTOMER_REPORTED_DRAFT_GAP'}
                    or any(row.get('claim_state') != 'CUSTOMER_ASSERTION_UNVERIFIED'
                           or any(row.get(field) for field in ('assigned_review_owner', 'verified_date', 'reviewer_disposition'))
                           for row in customer_rows)
                    or bool(regops_pack.get('deadline_and_renewal_queue'))):
                raise ValueError('DIO RegOps customer source register failed its row-binding or review-boundary checks')
            product_specific_refs.extend([
                register(regops_review_receipt), register(regops_processing_receipt), register(regops_review_pack), register(regops_review_register),
                register(regops_review_root / 'EXECUTION/REGOPS_READINESS_PACK.html'),
                register(regops_review_root / 'REGOPS_CUSTOMER_PROJECTION.json'), register(regops_review_source),
                register(ROOT / 'products/professional_evidence_native.py'), register(ROOT / 'products/regops/runner.py'),
            ])
            changes.append(f"DIO RegOps now compares the customer-stated return date with the review date ({review_date}) and flags it as a past-date candidate, without concluding the deadline applies or filing was late. It requests filing-status evidence, a submission receipt, and any extension/superseding notice. All four statements remain bound to exact source rows; dates and roles remain unverified, and no deadline was promoted into the readiness engine.")
            limits = ['The customer register binds source statements and provides review follow-ups; it does not verify truth, legal applicability, regulatory deadlines, filing authority, or owner appointment. The configured readiness result remains REFUSE and professional review is required.']
        if name == 'VAMP Performance' and vamp_objective_mapping_package.is_file():
            mapping_package = read_json(vamp_objective_mapping_package)
            product_specific_refs.extend([
                register(vamp_objective_mapping_package), register(vamp_objective_mapping_projection),
                register(vamp_objective_mapping_validation), register(vamp_objective_mapping_snapshot),
                register(vamp_objective_mapping_root / 'REVIEW_CONTENT.json'),
                register(vamp_objective_mapping_case_source),
            ])
            changes.append(f"The January-June VAMP run now recognizes all three supplied KPA objectives (KPA1, KPA3, KPA5) and proposes {mapping_package.get('candidate_source_mapping_count')} same-register-row evidence links. Exact source fragments are byte-verified; all links remain human-review candidates, with zero accepted mappings and no rating.")
            limits = ['The declared review period, extracted objectives and source-fragment anchors match the supplied register. Candidate links are not verified evidence; underlying artifacts, event dates, authenticity, sufficiency and achievement remain unverified. No employee rating or employment decision is made.']
        if name in VAMP_REVIEW_SURFACE_ROUTES and VAMP_REVIEW_SURFACE_ROUTES[name].is_dir():
            route_root = VAMP_REVIEW_SURFACE_ROUTES[name]
            native_receipt_path = route_root / 'NATIVE_CUSTOMER_PACKET_RECEIPT.json'
            pipeline_receipt_path = route_root / 'EXECUTION/PROFESSIONAL_VAMP_PIPELINE_RECEIPT.json'
            surface_root = route_root / 'EXECUTION/vamp_evidence_review'
            surface_receipt_path = surface_root / 'VAMP_EVIDENCE_REVIEW_SURFACE_RECEIPT.json'
            review_csv_path = surface_root / 'VAMP_EVIDENCE_REVIEW.csv'
            review_html_path = surface_root / 'VAMP_EVIDENCE_REVIEW.html'
            review_guide_path = surface_root / 'VAMP_EVIDENCE_REVIEW_GUIDE.md'
            review_tool_path = surface_root / 'VAMP_EVIDENCE_REVIEW_TOOL.py'
            projection_path = route_root / 'PROJECTION/VAMP_DOMAIN_PROJECTION.json'
            snapshot_candidates = sorted((route_root / 'EXECUTION/vamp_snapshot').glob('*/VAMP_SNAPSHOT.json'))
            snapshot_path = snapshot_candidates[0] if len(snapshot_candidates) == 1 else Path('/missing')
            binding_path = route_root / 'EXECUTION/VAMP_CUSTOMER_SNAPSHOT_BINDING.json'
            source_register_path = route_root / 'CUSTOMER_PACKET/SOURCES/02_evidence_register.csv'
            required_paths = [native_receipt_path, pipeline_receipt_path, surface_receipt_path, review_csv_path,
                              review_html_path, review_guide_path, review_tool_path, projection_path, snapshot_path, binding_path,
                              source_register_path]
            if not all(path.is_file() for path in required_paths):
                raise ValueError('VAMP Performance review-surface route is missing required artifacts')
            native_run = read_json(native_receipt_path)
            pipeline_run = read_json(pipeline_receipt_path)
            surface_receipt = read_json(surface_receipt_path)
            projection = read_json(projection_path)
            snapshot = read_json(snapshot_path)
            snapshot_binding = read_json(binding_path)
            source_bytes = source_register_path.read_bytes()
            source_sha = hashlib.sha256(source_bytes).hexdigest()
            with review_csv_path.open(encoding='utf-8-sig', newline='') as handle:
                review_rows = list(csv.DictReader(handle))
            exact_candidate_spans = []
            for review_row in review_rows:
                try:
                    anchor = str(review_row.get('source_ref') or '').rsplit('#bytes=', 1)[1]
                    start, end = (int(value) for value in anchor.split(':', 1))
                except (IndexError, ValueError):
                    start, end = -1, -1
                statement = str(review_row.get('customer_statement') or '')
                exact_candidate_spans.append(
                    start >= 0 and end > start and end <= len(source_bytes)
                    and source_bytes[start:end].decode('utf-8') == statement
                    and review_row.get('source_file_sha256') == source_sha
                    and hashlib.sha256(source_bytes[start:end]).hexdigest() == review_row.get('source_statement_sha256')
                )
            surface_artifacts_match = all(
                (surface_root / str(item.get('path') or '')).is_file()
                and digest_file(surface_root / str(item.get('path') or '')) == item.get('sha256')
                for item in (surface_receipt.get('artifacts') or {}).values()
            )
            candidate_pairs = {
                (str(row.get('evidence_id') or ''), str(row.get('candidate_task_id') or ''))
                for row in projection.get('rows') or [] if row.get('candidate_task_id')
            }
            output_pairs = {(str(row.get('evidence_id') or ''), str(row.get('objective_id') or '')) for row in review_rows}
            expected_route = 'vamp_raw_performance' if name == 'VAMP Performance' else 'vamp_raw_profile'
            if (native_run.get('product_name') != name
                    or native_run.get('route') != expected_route
                    or native_run.get('release_authorized') is not False
                    or native_run.get('external_effects') is not False
                    or pipeline_run.get('external_release_gate') != 'REFUSE'
                    or pipeline_run.get('authority_created') is not False
                    or pipeline_run.get('external_effects') is not False
                    or surface_receipt.get('schema') != 'dio.vamp.evidence_relevance_review_surface.v1'
                    or surface_receipt.get('packet_fingerprint') != snapshot_binding.get('packet_fingerprint')
                    or surface_receipt.get('snapshot_sha256') != digest_file(snapshot_path)
                    or surface_receipt.get('customer_snapshot_binding_sha256') != digest_file(binding_path)
                    or surface_receipt.get('candidate_count') != len(review_rows)
                    or output_pairs != candidate_pairs
                    or surface_receipt.get('review_state') != 'PENDING_HUMAN_REVIEW'
                    or surface_receipt.get('accepted_evidence_count') != 0
                    or surface_receipt.get('rating_generated') is not False
                    or surface_receipt.get('employment_decision_generated') is not False
                    or surface_receipt.get('external_release_authorized') is not False
                    or any(row.get('decision') or row.get('reviewer_name') or row.get('reviewer_role')
                           or row.get('reviewed_at_iso8601') or row.get('rationale') for row in review_rows)
                    or any(row.get('event_date_verified') == 'true' and row.get('underlying_artifact_received') != 'true'
                           for row in review_rows)
                    or not all(token in review_html_path.read_text(encoding='utf-8') for token in
                               ("data-field='reviewer_role'", "data-field='reviewed_at_iso8601'",
                                'event date cannot be marked verified until the underlying artifact'))
                    or not exact_candidate_spans or not all(exact_candidate_spans)
                    or not surface_artifacts_match
                    or (pipeline_run.get('evidence_relevance_review') or {}).get('receipt_sha256') != digest_file(surface_receipt_path)):
                raise ValueError('VAMP evidence relevance review is stale, unbound, or crossed its non-authorizing boundary')
            product_specific_refs.extend(register(path) for path in required_paths)
            product_specific_refs.extend(register(path) for path in [
                surface_root / 'VAMP_EVIDENCE_REVIEW.csv', surface_root / 'VAMP_EVIDENCE_REVIEW.html',
                surface_root / 'VAMP_EVIDENCE_REVIEW_GUIDE.md',
                ROOT / 'products/vamp_review_surface.py',
                ROOT / 'products/professional_evidence_customer_surface_compat.py',
                ROOT / 'products/professional_evidence_final_compat.py',
                ROOT / 'products/native_customer_runner.py',
            ])
            changes.append(f"{name} now ships an offline, source-byte-bound relevance review for all {len(review_rows)} candidate evidence links, with exact statement/file hashes, reviewer name and role, an explicit timezone-aware review time, and artifact/date fields. The worksheet prevents a date verification claim unless the artifact was received. All mappings remain unaccepted, and rating/employment/release authority stays disabled.")
            limits.append('A recorded relevance decision does not establish source authenticity, event date, evidence sufficiency or objective achievement. The synthetic sample remains unverified and no performance rating or employment decision is made.')
        customer_deliverables = list(capabilities[key]['customer_deliverable_refs']) if key else []
        if specialist_qualification_root is not None:
            customer_deliverables.extend(str(path.relative_to(ROOT)) for path in sorted((specialist_qualification_root / 'normal/customer_delivery').glob('*'))
                                         if path.is_file() and path.suffix.lower() in {'.docx', '.html', '.pdf'})
        if name == 'Site Studio' and site_studio_accessibility is not None and not SITE_STUDIO_PROFESSIONAL_DRAFT_RUN.is_dir():
            customer_deliverables.append(str((SITE_STUDIO_ACCESSIBILITY_RUN / 'site-studio/site-studio/EXECUTION/site_draft/marketfront/index.html').relative_to(ROOT)))
        if name == 'Site Studio' and SITE_STUDIO_PROFESSIONAL_DRAFT_RUN.is_dir():
            customer_deliverables.extend(str(path.relative_to(ROOT)) for path in [
                SITE_STUDIO_PROFESSIONAL_DRAFT_RUN / 'EXECUTION/site_draft/marketfront/index.html',
                SITE_STUDIO_PROFESSIONAL_DRAFT_RUN / 'EXECUTION/site_draft/marketfront/styles.css',
                SITE_STUDIO_PROFESSIONAL_DRAFT_RUN / 'EXECUTION/site_draft/site-review/CUSTOMER_REVIEW_NOTES.md',
                SITE_STUDIO_PROFESSIONAL_DRAFT_RUN / 'CUSTOMER_SITE_PREVIEW_README.md',
                SITE_STUDIO_PROFESSIONAL_DRAFT_RUN / 'CUSTOMER_SITE_DRAFT_PACKAGE.zip',
                SITE_STUDIO_PROFESSIONAL_DRAFT_RUN / 'RENDERED_REVIEW_EVIDENCE.json',
            ] if path.is_file())
        if name == 'Launch Studio' and LAUNCH_STUDIO_CUSTOMER_REVIEW_BUNDLE.is_dir():
            customer_deliverables.extend(str(path.relative_to(ROOT)) for path in [
                LAUNCH_STUDIO_CUSTOMER_REVIEW_BUNDLE / 'index.html',
                LAUNCH_STUDIO_CUSTOMER_REVIEW_BUNDLE / 'README.md',
                LAUNCH_STUDIO_CUSTOMER_REVIEW_BUNDLE / 'BUNDLE_MANIFEST.json',
                LAUNCH_STUDIO_CUSTOMER_REVIEW_BUNDLE.with_suffix('.zip'),
            ] if path.is_file())
        if name == 'Offer Lab' and offer_lab_source_review is not None:
            customer_deliverables.extend(str((OFFER_LAB_SOURCE_REVIEW_RUN / 'offer-lab/offer-lab/EXECUTION' / filename).relative_to(ROOT))
                                         for filename in ('OFFER_REVIEW.html', 'OFFER_REVIEW_WORKSHEET.csv',
                                                          'OFFER_REVIEW_VALIDATOR.py', 'OFFER_REVIEW_VALIDATION.json',
                                                          'BOUNDED_OFFER.md'))
        if name == 'Vesper Desk' and vesper_source_review is not None:
            customer_deliverables.extend(str((VESPER_DESK_SOURCE_REVIEW_RUN / 'vesper-desk/vesper-desk/EXECUTION' / filename).relative_to(ROOT))
                                         for filename in ('VESPER_REVIEW.html', 'VESPER_REVIEW_WORKSHEET.csv', 'VESPER_DRAFT_NEXT_STEP.md'))
        if name == 'DossierOps' and dossierops_review_surface is not None:
            customer_deliverables.extend(str((DOSSIEROPS_REVIEW_SURFACE_ROUTE / 'dossierops/dossierops/EXECUTION' / filename).relative_to(ROOT))
                                         for filename in ('DOSSIEROPS_DOSSIER_INDEX.html', 'DOSSIEROPS_CONTROLLED_DOSSIER.zip'))
        if name == 'Opportunity Foundry' and opportunity_foundry_review is not None:
            customer_deliverables.extend(str((OPPORTUNITY_FOUNDRY_REVIEW_ROUTE / 'opportunity-foundry/EXECUTION' / filename).relative_to(ROOT))
                                         for filename in ('OPPORTUNITY_FOUNDRY_REVIEW.html', 'OPPORTUNITY_FOUNDRY_BRIEF.md'))
        if name in EVIDENCE_PROFILE_REVIEW_SURFACE_PRODUCTS and profile_review_surface is not None:
            profile_slug = re.sub(r'[^a-z0-9]+', '-', name.lower()).strip('-')
            profile_case = EVIDENCE_PROFILE_REVIEW_SURFACE_BATCH / profile_slug / profile_slug
            customer_deliverables.append(str(next((profile_case / 'EXECUTION').glob('*_REVIEW_PACK.html')).relative_to(ROOT)))
        if name in {'Agent Authority', 'ChangeProof', 'DIO AI Assurance'} and ai_trust_review is not None:
            ai_folder = {'Agent Authority': ('agent-authority', 'agent-authority/agent-authority', 'EXECUTION'),
                         'ChangeProof': ('changeproof', 'changeproof/changeproof', 'EXECUTION'),
                         'DIO AI Assurance': ('dio-ai-assurance', 'dio-ai-assurance', 'EXECUTION/component_aitrustproof')}[name]
            ai_case = AI_TRUST_REVIEW_SURFACE_BATCH / ai_folder[1]
            ai_exec = ai_case / ai_folder[2]
            customer_deliverables.extend(str((ai_exec / filename).relative_to(ROOT))
                                         for filename in ('AI_TRUST_DOSSIER.html', 'AI_TRUST_DOSSIER.pdf', 'AI_TRUST_DOSSIER.docx'))
        if name == 'Contract Desk' and contract_date_scenario_root.is_dir():
            customer_deliverables.extend(str(path.relative_to(ROOT)) for path in sorted((contract_date_scenario_root / 'customer_delivery').glob('*')) if path.suffix in {'.docx', '.html', '.pdf'})
        if name == 'VAMP Performance' and vamp_objective_mapping_root.is_dir():
            customer_deliverables.extend(str(path.relative_to(ROOT)) for path in sorted((vamp_objective_mapping_root / 'customer_delivery').glob('*')) if path.suffix in {'.docx', '.html', '.pdf'})
        if name in VAMP_REVIEW_SURFACE_ROUTES and VAMP_REVIEW_SURFACE_ROUTES[name].is_dir():
            customer_deliverables.extend(str(path.relative_to(ROOT)) for path in [
                VAMP_REVIEW_SURFACE_ROUTES[name] / 'EXECUTION/vamp_evidence_review/VAMP_EVIDENCE_REVIEW.html',
                VAMP_REVIEW_SURFACE_ROUTES[name] / 'EXECUTION/vamp_evidence_review/VAMP_EVIDENCE_REVIEW.csv',
                VAMP_REVIEW_SURFACE_ROUTES[name] / 'EXECUTION/vamp_evidence_review/VAMP_EVIDENCE_REVIEW_GUIDE.md',
                VAMP_REVIEW_SURFACE_ROUTES[name] / 'EXECUTION/vamp_evidence_review/VAMP_EVIDENCE_REVIEW_TOOL.py',
            ])
        if name == 'DIO RegOps' and regops_review_root.is_dir():
            customer_deliverables.extend(str(path.relative_to(ROOT)) for path in [regops_review_root / 'EXECUTION/REGOPS_READINESS_PACK.html', regops_review_root / 'EXECUTION/REGOPS_CUSTOMER_REVIEW_REGISTER.csv'] if path.is_file())
        readiness_source_run = READINESS_SOURCE_ISSUE_RUNS.get(name)
        if name == 'EntrepreneurProof':
            readiness_source_run = ENTREPRENEURPROOF_SOURCE_ISSUE_RUN
        if readiness_source_run and readiness_source_run.is_dir():
            customer_deliverables.extend(str(path.relative_to(ROOT)) for path in sorted((readiness_source_run / 'customer_delivery').glob('*'))
                                         if path.is_file() and path.suffix.lower() in {'.docx', '.html', '.pdf'})
            workbook = readiness_source_run / 'FINANCIAL_REVIEW_WORKBOOK.xlsx'
            if workbook.is_file():
                customer_deliverables.append(str(workbook.relative_to(ROOT)))
        issue_review_run = READINESS_ISSUE_REVIEW_SURFACES.get(name)
        if issue_review_run and issue_review_run.is_dir():
            customer_deliverables.extend(str((issue_review_run / filename).relative_to(ROOT))
                                         for filename in ('READINESS_ISSUE_REVIEW.html', 'READINESS_ISSUE_REVIEW.csv')
                                         if (issue_review_run / filename).is_file())
        if name == 'Corporate Readiness' and CORPORATE_READINESS_ACTION_RUN.is_dir():
            customer_deliverables.extend(str(path.relative_to(ROOT)) for path in [
                CORPORATE_READINESS_ACTION_RUN / 'CORPORATE_CUSTOMER_ACTION_REGISTER.csv',
                CORPORATE_READINESS_ACTION_RUN / 'DOCUMENT_REQUESTS.json',
            ] if path.is_file())
        if name == 'Campaign Lab' and CAMPAIGN_LAB_REVIEW_SURFACE.is_dir():
            customer_deliverables.append(str((CAMPAIGN_LAB_REVIEW_SURFACE / 'CAMPAIGN_LAB_REVIEW.html').relative_to(ROOT)))
        if name in {'Sophia Integrity', 'Sophia Research', 'Sophia Review', 'Sophia Supervisor', 'Sophia Tutor'} and SOPHIA_SERAPH_LIVE_PROCESS_BATCH.is_dir():
            product_slug = name.casefold().replace(' ', '-')
            live_root = SOPHIA_SERAPH_LIVE_PROCESS_BATCH / product_slug
            customer_deliverables.extend(str(path.relative_to(ROOT)) for path in sorted((live_root / 'EXECUTION/profile_review').glob('*_REVIEW_PACK.html')))
            native_root = live_root / 'EXECUTION/sophia_native'
            customer_deliverables.extend(str(path.relative_to(ROOT)) for path in sorted(native_root.rglob('CLAIM_SOURCE_LEDGER.md')))
            customer_deliverables.extend(str(path.relative_to(ROOT)) for path in sorted(native_root.rglob('REVIEWER_COMMENTARY.md')))
            customer_deliverables.extend(str(path.relative_to(ROOT)) for path in sorted(native_root.rglob('*SOPHIA_REVIEW_PACK.zip')))
        if name == 'FundingFinder' and FUNDING_FINDER_THREE_WINDOW_DATA.is_file():
            customer_deliverables.extend(str(path.relative_to(ROOT)) for path in [
                FUNDING_FINDER_THREE_WINDOW_RUN / 'FUNDINGFINDER_SERVICESETA_WINDOWS.html',
                FUNDING_FINDER_THREE_WINDOW_RUN / 'APPLICANT_WINDOW_REVIEW.csv',
                FUNDING_FINDER_THREE_WINDOW_DATA,
            ] if path.is_file())
        if name == 'HOMS Exam':
            exam_pack = ROOT / 'deliverables/homs_random_grade_exam_set_20261101'
            customer_deliverables.extend(str(path.relative_to(ROOT)) for path in [
                exam_pack / 'index.html',
                exam_pack / 'HOMS_RANDOM_GRADE_EXAMS_AND_MEMOS_PRINT_READY_20261101.zip',
            ] if path.is_file())
            customer_deliverables.extend(str(path.relative_to(ROOT)) for path in [
                HOMS_BEST_EXAM_CANDIDATE_SHORTLIST.with_suffix('.md'),
                HOMS_BEST_EXAM_CANDIDATE_SHORTLIST,
            ] if path.is_file())
            customer_deliverables.extend(str(path.relative_to(ROOT)) for path in [
                HOMS_CURATED_CANDIDATE_BUNDLE / 'index.html',
                HOMS_CURATED_CANDIDATE_BUNDLE / 'README.md',
                HOMS_CURATED_CANDIDATE_BUNDLE / 'HOMS_RANDOMIZED_EXAM_CANDIDATES_GRADES_01_12.zip',
            ] if path.is_file())
        if name == 'HOMS Moderate' and HOMS_MODERATE_MASTER_INDEX.is_file():
            customer_deliverables.append(str(HOMS_MODERATE_MASTER_INDEX.relative_to(ROOT)))
        if name == 'HOMS Learning Studio' and HOMS_LEARNING_STUDIO_MASTER_INDEX.is_file():
            customer_deliverables.append(str(HOMS_LEARNING_STUDIO_MASTER_INDEX.relative_to(ROOT)))
        if name == 'HOMS Assess' and HOMS_ASSESS_INTERACTIVE_EDUCATOR_RUN.is_dir():
            customer_deliverables.extend(str(path.relative_to(ROOT)) for path in [
                HOMS_ASSESS_INTERACTIVE_EDUCATOR_RUN / 'CUSTOMER_ASSESS_REVIEW.html',
                HOMS_ASSESS_INTERACTIVE_EDUCATOR_RUN / 'educator_review/index.html',
                HOMS_ASSESS_INTERACTIVE_EDUCATOR_RUN / 'educator_review/EDUCATOR_POINTWISE_ADJUDICATION.csv',
                HOMS_ASSESS_INTERACTIVE_EDUCATOR_RUN / 'educator_review/EDUCATOR_POINTWISE_ADJUDICATION_GUIDE.md',
            ] if path.is_file())
        if name == 'HOMS Assess' and HOMS_ASSESS_QUOTE_SUGGESTIONS.is_file():
            suggestion_evidence = read_json(HOMS_ASSESS_QUOTE_SUGGESTIONS)
            suggestion_outputs = suggestion_evidence.get('outputs') or {}
            customer_deliverables.extend(suggestion_outputs[key] for key in ('review_page', 'adjudication_csv', 'educator_guide')
                                         if key in suggestion_outputs and (ROOT / suggestion_outputs[key]).is_file())
        if name == 'ContractProof':
            contract_root = OUTPUT / 'CONTRACTPROOF_CUSTOMER_EXECUTION_20261102_V1'
            customer_deliverables.extend(str(path.relative_to(ROOT)) for path in [
                contract_root / 'contractproof/EVIDENCE_PACK.html',
                contract_root / 'contractproof/EVIDENCE_PACK.pdf',
                contract_root / 'CUSTOMER_NEXT_STEP_DRAFT.md',
            ] if path.is_file())
        if name in {'GrantProof', 'PermitProof', 'PolicyProof', 'TenderProof'}:
            obligation_root = OUTPUT / 'OBLIGATION_FAMILY_CUSTOMER_EXECUTIONS_20261102_V2' / name.casefold()
            customer_deliverables.extend(str(path.relative_to(ROOT)) for path in [
                obligation_root / 'evidence_pack/EVIDENCE_PACK.html',
                obligation_root / 'evidence_pack/EVIDENCE_PACK.pdf',
                obligation_root / 'evidence_pack/EVIDENCE_PACK.docx',
            ] if path.is_file())
            _, source_review_root = OBLIGATION_FAMILY_SOURCE_REVIEWS[name]
            customer_deliverables.extend(str(path.relative_to(ROOT)) for path in [
                source_review_root / 'evidence_pack/EVIDENCE_PACK.html',
                source_review_root / 'evidence_pack/EVIDENCE_PACK.pdf',
                source_review_root / 'evidence_pack/EVIDENCE_PACK.docx',
                source_review_root / f'{name.upper()}_SOURCE_ALIGNMENT_EVIDENCE.json',
            ] if path.is_file())
        if name == 'HOMS Accreditation':
            accreditation_root = OUTPUT / 'HOMS_ACCREDITATION_CUSTOMER_PACKET_EXECUTION_20261101_V4/customer_delivery'
            customer_deliverables.extend(str(path.relative_to(ROOT)) for path in sorted(accreditation_root.glob('customer-*-en.*'))
                                         if path.suffix.lower() in {'.docx', '.html', '.pdf'})
            customer_deliverables.extend(str(path.relative_to(ROOT)) for path in [
                HOMS_ACCREDITATION_REVIEW_WORKSPACE, HOMS_ACCREDITATION_REVIEW_WORKSHEET,
            ] if path.is_file())
        if name == 'Market Radar':
            market_root = OUTPUT / 'MARKET_RADAR_CUSTOMER_EXECUTION_20261104_V3/EXECUTION'
            customer_deliverables.extend(str(path.relative_to(ROOT)) for path in [
                market_root / 'MARKET_RADAR_TARGET_BRIEF.md',
                market_root / 'MARKET_RADAR_TARGET_BRIEF.json',
            ] if path.is_file())
        if name == 'HOMS Curriculum' and HOMS_CURRICULUM_MASTER_INDEX.is_file():
            customer_deliverables.append(str(HOMS_CURRICULUM_MASTER_INDEX.relative_to(ROOT)))
        if name == 'Document Studio Localize' and DOCUMENT_STUDIO_LOCALIZE_CUSTOMER_DEMO.is_dir():
            localize_root = DOCUMENT_STUDIO_LOCALIZE_CUSTOMER_DEMO / 'document_studio/DIO_LOCALIZE_V6'
            customer_deliverables.extend(str(path.relative_to(ROOT)) for path in [
                localize_root / 'formatted/Afrikaans/lingua-dio-localize-v6-afrikaans.html',
                localize_root / 'formatted/Afrikaans/lingua-dio-localize-v6-afrikaans.pdf',
                localize_root / 'pdf/BILINGUAL_REVIEW_COPY.pdf',
                localize_root / 'LINGUA_HUMAN_REVIEW_TEMPLATE.json',
                DOCUMENT_STUDIO_LOCALIZE_REVIEW_WORKSPACE,
                localize_root / 'DIO_LOCALIZE_V6_DOCUMENT_STUDIO_REVIEW_PACK.zip',
            ] if path.is_file())
        if name == 'Document Studio Publish' and DOCUMENT_STUDIO_PUBLISH_CUSTOMER_DEMO.is_dir():
            customer_deliverables.extend(str(path.relative_to(ROOT)) for path in [
                DOCUMENT_STUDIO_PUBLISH_CUSTOMER_DEMO / 'PUBLICATION_REVIEW.html',
                DOCUMENT_STUDIO_PUBLISH_CUSTOMER_DEMO / 'formatted/publication-14c0fe40557275d3-english.html',
                DOCUMENT_STUDIO_PUBLISH_CUSTOMER_DEMO / 'formatted/publication-14c0fe40557275d3-english.pdf',
                DOCUMENT_STUDIO_PUBLISH_CUSTOMER_DEMO / 'formatted/publication-14c0fe40557275d3-english.docx',
            ] if path.is_file())
        if name == 'Document Studio Edit' and DOCUMENT_STUDIO_EDIT_CUSTOMER_DEMO.is_dir():
            edit_root = DOCUMENT_STUDIO_EDIT_CUSTOMER_DEMO / 'document_studio/CUSTOMER-DSE-20261106-V2'
            customer_deliverables.extend(str(path.relative_to(ROOT)) for path in [
                edit_root / 'pdf/REDLINE_REVIEW_COPY.pdf',
                edit_root / 'pdf/CLEAN_EDITED_COPY.pdf',
                edit_root / 'TECHNICAL_EDIT_REVIEW_TEMPLATE.csv',
                DOCUMENT_STUDIO_EDIT_REVIEW_WORKSPACE,
                edit_root / 'CUSTOMER-DSE-20261106-V2_DOCUMENT_STUDIO_REVIEW_PACK.zip',
            ] if path.is_file())
        if name == 'Accessible Publish' and ACCESSIBLE_PUBLISH_CUSTOMER_DEMO.is_dir():
            customer_deliverables.extend(str(path.relative_to(ROOT)) for path in [
                ACCESSIBLE_PUBLISH_CUSTOMER_DEMO / 'PREPARED_REVIEW.html',
                ACCESSIBLE_PUBLISH_CUSTOMER_DEMO / 'ACCESSIBILITY_REVIEW.html',
                ACCESSIBLE_PUBLISH_CUSTOMER_DEMO / 'OWNER_REMEDIATION_REQUEST.md',
            ] if path.is_file())
        if name == 'Accessible Publish' and ACCESSIBLE_PUBLISH_LIVE_BROWSER_DEMO.is_dir():
            customer_deliverables.extend(str(path.relative_to(ROOT)) for path in [
                ACCESSIBLE_PUBLISH_LIVE_BROWSER_DEMO / 'ACCESSIBILITY_REVIEW.html',
                ACCESSIBLE_PUBLISH_LIVE_BROWSER_DEMO / 'OWNER_REMEDIATION_REQUEST.md',
            ] if path.is_file())
        if name == 'Accessible Publish' and ACCESSIBLE_PUBLISH_CUSTOMER_REVIEW_BUNDLE.is_dir():
            customer_deliverables.extend(str(path.relative_to(ROOT)) for path in [
                ACCESSIBLE_PUBLISH_CUSTOMER_REVIEW_BUNDLE / 'index.html',
                ACCESSIBLE_PUBLISH_CUSTOMER_REVIEW_BUNDLE / 'README.md',
                ACCESSIBLE_PUBLISH_CUSTOMER_REVIEW_BUNDLE / 'BUNDLE_MANIFEST.json',
                ACCESSIBLE_PUBLISH_CUSTOMER_REVIEW_BUNDLE.with_suffix('.zip'),
            ] if path.is_file())
        rows.append({
            'name': name, 'product_id': old.get('product_id'), 'suite': old.get('suite'),
            'catalog_contract': catalog_row, 'historical_baseline': old,
            'historical_artifact_refs': historical_refs,
            'current_execution_override': current,
            'latest_full_pipeline_route_execution': current_full,
            'current_native_canon_extension_product_grade': (
                batch['products'][name] if native_extension_batch and name in native_extension_names else None
            ),
            'full_pipeline_route_freshly_rerun': current_full is not None,
            'canonical_execution_freshly_rerun': current is not None,
            'customer_preparation_examples_current': key is not None,
            'current_disposition': disposition, 'current_changes': changes,
            'pilot_candidate': key is not None, 'distinct_capability_id': key,
            'shared_capability_offer_names': capabilities[key]['offers'] if key else [],
            'current_artifact_refs': capabilities[key]['artifact_refs'] if key else [],
            'current_product_specific_evidence_refs': product_specific_refs,
            'customer_deliverable_refs': customer_deliverables,
            'quality_limits': limits, 'independent_professional_signoff': False,
            'buyer_acceptance': 'NOT_ESTABLISHED', 'commercial_validation': 'UNPROVED',
            'qualification_grants_release_authority': False,
        })

    return {
        'schema': 'dio.customer_product_qualification.v1',
        'generated_at': datetime.now(timezone.utc).replace(microsecond=0).isoformat(),
        'evidence_as_of': datetime.now(timezone.utc).date().isoformat(),
        'source_snapshot_basis': 'Historical assessments are retained. Current 68-offer route execution and supplemental artifact/source binding checks are linked from the 2026-11-02 synthetic execution report; focused pilot assessment groups remain separate. This generator does not rerun products or grant qualification.',
        'summary': {
            'offer_count': len(rows), 'operator_assessed_pilot_named_offers': len(pilot_map),
            'distinct_pilot_capabilities': len(capabilities),
            'customer_packet_contract_count': sum(bool(row['customer_packet_execution_available']) for row in catalog),
            'offers_retaining_existing_native_protocol': sum(not row['customer_packet_execution_available'] for row in catalog),
            'independent_professional_signoffs': 0, 'independent_professional_signoff_denominator': 68,
            'current_native_canonical_extensions_verified': len(native_extension_names),
            'native_canonical_extension_denominator': baseline['extension_count'],
            'fresh_canonical_named_offers': len(fresh_by_offer),
            'historical_canonical_execution_retained_named_offers': len(rows) - len(fresh_by_offer),
            'current_full_pipeline_route_offers_verified': len(full_by_offer),
            'current_full_pipeline_route_offer_denominator': len(rows),
            'current_disposition_counts': dict(Counter(row['current_disposition'] for row in rows)),
        },
        'qualification_basis': {
            'kind': 'Provisional operator assessment for a bounded professionally delivered paid pilot with human review.',
            'assessment_source': audit_ref, 'historical_baseline_source': baseline_ref,
            'named_offer_aliases_count_separately': True,
            'shared_capabilities_do_not_multiply_independent_evidence': True,
            'professional_acceptance': 'NOT_ESTABLISHED', 'buyer_willingness_to_pay': 'UNPROVED',
            'all_68_fresh_execution_claimed': len(full_by_offer) == 68, 'full_repository_suite_green_claimed': False,
            'all_68_current_route_executions_verified': len(full_by_offer) == 68,
            'native_extension_canonical_proof_recovered_claimed': len(native_extension_names) == 11,
            'publication_or_professional_authority_created': False,
        },
        'current_execution_evidence_groups': run_groups,
        'capabilities': capabilities, 'products': rows,
        'evidence_artifacts': sorted(evidence_index.values(), key=lambda value: value['path']),
        'remaining_gaps': [
            'Independent expert and customer acceptance of the pilot examples; willingness to pay remains unproved.',
            'Proficient Afrikaans language approval remains pending despite successful packaging.',
            'HOMS assessment reasoning quality remains unresolved.',
            f"Current native extension native ProductGrade is {len(native_extension_names)}/11; commercial validation and external acceptance remain unproved.",
            'PromotionProof and CPDProof route execution passes on synthetic declared periods; actual source records, accepted mappings, and professional interpretation remain outstanding.',
            'The full repository suite is not green; focused verification does not resolve all historical failures.',
        ],
    }


def build_html(report: dict) -> str:
    e = lambda value: html.escape(str(value), quote=True)

    def link(ref: str, label: str) -> str:
        relative = os.path.relpath(ROOT / ref, OUTPUT)
        return f'<a href="{e(quote(relative, safe="/.-_"))}">{e(label)}</a>'

    rows = []
    for row in report['products']:
        current = row['current_execution_override']
        fresh = f"Specific pilot variants: {current['verified_count']}/{current['variant_count']} verified" if current else 'Specific pilot variants: historical record retained; no current variant-level override'
        if current and not current['all_variants_verified']:
            fresh += ' — missing review dates refused'
        route = row.get('latest_full_pipeline_route_execution')
        if route:
            fresh += '; current full-pipeline customer route: PASS (synthetic, review held)'
        evidence = []
        if current:
            evidence.append(link(current['receipt'], 'Current execution receipt'))
        if route:
            evidence.append(link(route['receipt'], 'Current full-pipeline route receipt'))
        if row['name'] == 'HOMS Assess' and HOMS_ASSESS_QUALITY_REPORT.is_file():
            evidence.append(link(str(HOMS_ASSESS_QUALITY_REPORT.relative_to(ROOT)), 'HOMS feedback quality gate'))
        for ref in row.get('current_product_specific_evidence_refs', []):
            label = 'HOMS randomized exam set' if ref.endswith('/index.html') else 'Current product evidence'
            evidence.append(link(ref, label))
        # Deliberately link only public-facing customer surfaces here. Raw
        # sources and private signing records never enter the HTML report.
        pdfs = [ref for ref in row['customer_deliverable_refs'] if ref.endswith('.pdf')]
        examples = pdfs[:2] or row['customer_deliverable_refs'][:2]
        evidence.extend(link(ref, f'Example {index + 1}') for index, ref in enumerate(examples))
        if row['pilot_candidate']:
            label = 'Pilot candidate · review required'
        elif current and not current['all_variants_verified']:
            label = 'Blocked: actual dates required'
        elif current:
            label = 'Held preparation · further quality review'
        else:
            label = 'Historical qualification retained'
        contract = row['catalog_contract']['customer_packet_contract'] or 'Existing native protocol'
        historical = row['historical_baseline']
        historical_text = f"Historical grade: {historical['quality_status']}. {len(historical.get('findings', []))} original findings retained in the JSON ledger."
        details = ''.join(f'<p>{e(change)}</p>' for change in row['current_changes'])
        details += '<p>' + e(historical_text) + '</p>'
        evidence_html = ' · '.join(evidence) or 'Historical source references retained in JSON'
        search = ' '.join([row['name'], row['suite'] or '', label, contract]).casefold()
        rows.append(f'<tr data-search="{e(search)}" data-pilot="{str(row["pilot_candidate"]).lower()}"><th scope="row">{e(row["name"])}<small>{e(row["suite"])}</small></th><td><strong>{e(label)}</strong><p>{e(fresh)}</p><details><summary>Assessment history</summary>{details}</details></td><td>{e(contract)}</td><td>{"".join("<p>" + e(limit) + "</p>" for limit in row["quality_limits"])}</td><td>{evidence_html}</td></tr>')

    summary = report['summary']
    cards = ''.join(f'<div class="stat"><strong>{e(value)}</strong><span>{e(label)}</span></div>' for value, label in [
        (f"{summary['operator_assessed_pilot_named_offers']}/68", 'named pilot candidates'),
        (summary['distinct_pilot_capabilities'], 'distinct pilot capabilities'),
        (summary['customer_packet_contract_count'], 'customer packet contracts'),
        (f"{summary.get('current_full_pipeline_route_offers_verified', 0)}/{summary.get('current_full_pipeline_route_offer_denominator', 68)}", 'current full-pipeline route passes'),
        ('0/68', 'independent professional sign-offs'),
        (f"{summary.get('current_native_canonical_extensions_verified', 0)}/{summary.get('native_canonical_extension_denominator', 11)}", 'current native extension ProductGrade')])
    groups = ''.join(f'<li>{e(key.replace("_", " "))}: {value["verified_journey_count"]}/{value["journey_count"]} journeys verified; {value["refused_journey_count"]} refused. {link(value["source"], "Receipt")}</li>' for key, value in report['current_execution_evidence_groups'].items())
    gaps = ''.join(f'<li>{e(gap)}</li>' for gap in report['remaining_gaps'])
    return f'''<!doctype html>
<html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>DIO · 68-product qualification</title>
<style>body{{margin:0;background:#f5f4ef;color:#182b2a;font:16px/1.55 system-ui,sans-serif}}main{{max-width:1450px;margin:auto;padding:40px 28px}}h1{{font-size:clamp(2rem,4vw,3.5rem);line-height:1.1;max-width:950px}}h2{{margin-top:2.2rem}}a{{color:#095e70}}.eyebrow{{font-size:.8rem;letter-spacing:.1em;text-transform:uppercase}}.intro{{max-width:980px;font-size:1.1rem}}.stats{{display:grid;grid-template-columns:repeat(auto-fit,minmax(175px,1fr));gap:14px;margin:28px 0}}.stat{{background:white;padding:20px;border:1px solid #cbd4ce;border-top:4px solid #21675e}}.stat strong{{display:block;font-size:2rem}}.stat span{{display:block;font-size:.88rem}}.note{{max-width:1000px;border-left:4px solid #a66a27;padding:12px 18px;background:#fff7e8}}label{{display:inline-block;margin:8px 18px 15px 0}}input[type=search]{{display:block;min-width:260px;max-width:100%;padding:11px;border:1px solid #839b95;font:inherit}}input:focus-visible,a:focus-visible,summary:focus-visible{{outline:3px solid #a66a27;outline-offset:3px}}.scroll{{overflow:auto;background:white}}table{{border-collapse:collapse;width:100%;min-width:1050px}}th,td{{padding:17px 14px;vertical-align:top;border-bottom:1px solid #ccd5cf;text-align:left}}thead th{{background:#163f3b;color:white;font-size:.85rem}}tbody th{{width:17%}}td{{font-size:.9rem}}td:nth-child(2){{width:25%}}td:nth-child(4){{width:27%}}small{{display:block;font-weight:400;color:#546963;margin-top:8px}}p{{margin:.4rem 0 .9rem}}details{{margin-top:12px}}summary{{cursor:pointer}}footer{{margin-top:28px;color:#52655e;font-size:.9rem}}[hidden]{{display:none!important}}@media(max-width:600px){{main{{padding:25px 16px}}.stats{{grid-template-columns:repeat(2,1fr)}}.stat{{padding:13px}}}}</style></head>
<body><main><p class="eyebrow">DIO · evidence as of {e(report['evidence_as_of'])}</p><h1>68 offers. Current route evidence. Twelve pilot candidates.</h1>
<p class="intro">A current synthetic run passed all 68 product routes through Vesper intake and the product executor. The operator assessment separately identifies twelve named offers across nine services for a professionally delivered paid pilot with human review. Buyer acceptance, independent professional sign-off and willingness to pay remain unproved.</p>
<div class="stats">{cards}</div><p class="note">A source-driven preparation route and passing execution receipt establish bounded preparation and traceability. They do not establish professional approval. Studio aliases share evidence. All generated work remains synthetic, review-held, and without external release authority.</p>
<p>{link(report['qualification_basis']['assessment_source'], 'Qualification audit')} · {link(report['qualification_basis']['historical_baseline_source'], 'Historical baseline')} · <a href="68_PRODUCT_QUALIFICATION.json">Full JSON ledger and SHA-256 evidence inventory</a></p>
<h2>Current execution evidence</h2><ul>{groups}</ul><p>{summary.get('current_full_pipeline_route_offers_verified', 0)} of 68 current synthetic full-pipeline route runs passed. {summary['fresh_canonical_named_offers']} offers also have newer, variant-specific pilot receipts; the remaining 58 retain historical variant assessments. Historical quality findings remain attached, and route passes do not qualify products or establish customer acceptance.</p>
<h2>Offer qualification</h2><label>Find an offer<input id="search" type="search" placeholder="Name, suite or contract"></label><label><input id="pilots" type="checkbox"> Show twelve pilot names only</label><p id="count" aria-live="polite">68 offers shown</p>
<div class="scroll" tabindex="0" role="region" aria-label="Scrollable offer qualification table"><table><thead><tr><th scope="col">Offer</th><th scope="col">Current assessment</th><th scope="col">Customer input contract</th><th scope="col">Quality limits and review</th><th scope="col">Evidence</th></tr></thead><tbody>{''.join(rows)}</tbody></table></div>
<h2>Remaining qualification gaps</h2><ul>{gaps}</ul><footer>Built {e(report['generated_at'])}. Hashes record the bytes read by the generator. Missing historical files and changed declared hashes remain explicit in the JSON inventory. No private source excerpts or signing records are embedded in this page.</footer></main>
<script>const search=document.getElementById('search'),pilots=document.getElementById('pilots'),rows=[...document.querySelectorAll('tbody tr')];function filter(){{let n=0;for(const row of rows){{row.hidden=!row.dataset.search.includes(search.value.toLowerCase())||(pilots.checked&&row.dataset.pilot!=='true');if(!row.hidden)n++;}}document.getElementById('count').textContent=n+' offers shown';}}search.addEventListener('input',filter);pilots.addEventListener('change',filter);</script></body></html>'''


def main() -> int:
    report = build_qualification()
    OUTPUT.mkdir(parents=True, exist_ok=True)
    (OUTPUT / '68_PRODUCT_QUALIFICATION.json').write_text(json.dumps(report, indent=2, ensure_ascii=False) + '\n', encoding='utf-8')
    (OUTPUT / 'index.html').write_text(build_html(report), encoding='utf-8')
    print(json.dumps({'summary': report['summary'], 'evidence_artifact_count': len(report['evidence_artifacts']),
                      'missing_evidence_files': sum(not row['exists'] for row in report['evidence_artifacts']),
                      'declared_hash_mismatches': sum(row.get('declared_hash_matches') is False for row in report['evidence_artifacts'])}, indent=2))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
