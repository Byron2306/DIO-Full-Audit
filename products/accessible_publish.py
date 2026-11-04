"""Source-preserving accessibility preparation for static HTML publications.

Automated checks cover a small, explicit subset of WCAG 2.2 signals. They do
not certify WCAG conformance, PDF/UA, or usability with assistive technology.
"""
from __future__ import annotations

import hashlib
import html
import json
import os
import re
import signal
import subprocess
import sys
from html.parser import HTMLParser
from pathlib import Path
from typing import Any, Mapping


W3C_SOURCE = 'https://www.w3.org/TR/WCAG22/'
MAX_SOURCE_BYTES = 8 * 1024 * 1024
LANG_RE = re.compile(r'^[A-Za-z]{2,8}(?:-[A-Za-z0-9]{1,8})*$')


def _isolated_scripted_review(source: str, viewport_specs: list[dict[str, Any]]) -> dict[str, Any]:
    """Run untrusted inline scripts in a disposable process with no network and a hard timeout."""
    worker = Path(__file__).with_name('accessible_publish_scripted_worker.py')
    proc = subprocess.Popen([sys.executable, str(worker)], stdin=subprocess.PIPE, stdout=subprocess.PIPE,
                            stderr=subprocess.DEVNULL, text=True, start_new_session=True)
    try:
        stdout, _ = proc.communicate(json.dumps({'source': source, 'viewports': viewport_specs}), timeout=22)
    except subprocess.TimeoutExpired:
        try:
            os.killpg(proc.pid, signal.SIGKILL)
        except ProcessLookupError:
            pass
        proc.communicate()
        return {'state': 'SCRIPTED_REVIEW_TIMEOUT', 'reviews': []}
    if proc.returncode != 0:
        return {'state': 'SCRIPTED_REVIEW_FAILED', 'reviews': []}
    try:
        result = json.loads(stdout)
    except (TypeError, ValueError):
        return {'state': 'SCRIPTED_REVIEW_FAILED', 'reviews': []}
    return result if isinstance(result, dict) else {'state': 'SCRIPTED_REVIEW_FAILED', 'reviews': []}


def sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def inspect_rendered_html(source: str, *, source_sha256: str) -> dict[str, Any]:
    """Inspect computed text contrast and keyboard focus in an isolated static Chromium render."""
    try:
        from playwright.sync_api import sync_playwright
    except ImportError:
        return {
            'schema': 'dio.accessible_publish.rendered_review.v1',
            'source_sha256': source_sha256,
            'runtime_state': 'BROWSER_UNAVAILABLE',
            'issues': [{'check': 'browser_runtime', 'criterion': 'supporting runtime', 'state': 'REVIEW_REQUIRED',
                        'detail': 'Playwright is unavailable; computed styles and keyboard focus were not inspected.'}],
            'conformance_claim': 'NONE',
        }
    inspect_script = r"""() => {
      const visible = el => {
        const s = getComputedStyle(el);
        return !!el.getClientRects().length && s.display !== 'none' && s.visibility !== 'hidden' && Number(s.opacity || 1) > 0;
      };
      const parse = value => {
        const m = String(value).match(/rgba?\(([^)]+)\)/i);
        if (!m) return null;
        const parts = m[1].replace(/\//g, ',').split(',').map(x => x.trim());
        const rgb = parts.slice(0, 3).map(x => x.endsWith('%') ? parseFloat(x) * 2.55 : parseFloat(x));
        const alpha = parts[3] === undefined ? 1 : (parts[3].endsWith('%') ? parseFloat(parts[3]) / 100 : parseFloat(parts[3]));
        if (rgb.some(x => !Number.isFinite(x)) || !Number.isFinite(alpha)) return null;
        return {rgb, alpha};
      };
      const blend = (top, bottom) => top.map((c, i) => c * top[3] + bottom[i] * (1 - top[3]));
      const luminance = rgb => {
        const c = rgb.map(x => x / 255).map(x => x <= 0.04045 ? x / 12.92 : Math.pow((x + 0.055) / 1.055, 2.4));
        return 0.2126 * c[0] + 0.7152 * c[1] + 0.0722 * c[2];
      };
      const ratio = (a, b) => {
        const l1 = luminance(a), l2 = luminance(b);
        return (Math.max(l1, l2) + 0.05) / (Math.min(l1, l2) + 0.05);
      };
      const composedBackground = el => {
        let bg = [255, 255, 255], image = false, translucentAncestor = false;
        const chain = [];
        for (let n = el; n && n.nodeType === 1; n = n.parentElement) chain.push(n);
        for (const n of chain.reverse()) {
          const s = getComputedStyle(n);
          if (s.backgroundImage && s.backgroundImage !== 'none') image = true;
          const color = parse(s.backgroundColor);
          if (color && color.alpha > 0) bg = blend([...color.rgb, color.alpha], bg);
          if (Number(s.opacity || 1) < 0.999 || s.filter !== 'none' || s.mixBlendMode !== 'normal') translucentAncestor = true;
        }
        return {bg, image, translucentAncestor};
      };
      const textRuns = [];
      const all = [...document.querySelectorAll('body *')];
      for (const el of all) {
        if (!visible(el) || el.closest('[aria-hidden="true"]')) continue;
        const ownText = [...el.childNodes].filter(n => n.nodeType === Node.TEXT_NODE).map(n => n.nodeValue || '').join(' ').replace(/\s+/g, ' ').trim();
        if (!ownText) continue;
        const style = getComputedStyle(el), fg = parse(style.color), bg = composedBackground(el);
        const selectorIndex = all.indexOf(el) + 1;
        const large = parseFloat(style.fontSize || '0') >= 24 || (parseFloat(style.fontSize || '0') >= 18.66 && (parseInt(style.fontWeight || '400', 10) >= 700 || style.fontWeight === 'bold'));
        if (!fg || bg.image || bg.translucentAncestor || fg.alpha < 0.999) {
          textRuns.push({index: selectorIndex, state: 'UNKNOWN', threshold: large ? 3 : 4.5, reason: bg.image ? 'background image or gradient' : 'transparency, filter, or unsupported color'});
          continue;
        }
        const effectiveFg = fg.alpha < 1 ? blend([...fg.rgb, fg.alpha], bg.bg) : fg.rgb;
        const measured = ratio(effectiveFg, bg.bg);
        const threshold = large ? 3 : 4.5;
        textRuns.push({index: selectorIndex, state: measured >= threshold ? 'PASS' : 'ACTION_REQUIRED', ratio: Math.round(measured * 100) / 100, threshold, large_text: large});
      }
      const focusables = [...document.querySelectorAll('a[href],button,input,select,textarea,summary,[tabindex]')]
        .filter(el => !el.disabled && el.tabIndex >= 0 && visible(el));
      return {textRuns, focusableCount: focusables.length, linkedStylesheetCount: document.querySelectorAll('link[rel~="stylesheet"]').length,
        scriptCount: document.querySelectorAll('script').length, viewport: {width: innerWidth, height: innerHeight}};
    }"""
    focus_script = r"""() => {
      const visible = el => {
        const s = getComputedStyle(el);
        return !!el.getClientRects().length && s.display !== 'none' && s.visibility !== 'hidden' && Number(s.opacity || 1) > 0;
      };
      const targets = [...document.querySelectorAll('a[href],button,input,select,textarea,summary,[tabindex]')]
        .filter(el => !el.disabled && el.tabIndex >= 0 && visible(el));
      const el = document.activeElement;
      const index = targets.indexOf(el);
      if (index < 0) return null;
      // Read the computed style on the focused element. A pseudo-element style
      // query for :focus-visible returns empty values in Chromium.
      const style = getComputedStyle(el);
      const focusVisible = el.matches(':focus-visible');
      const indicator = focusVisible && ((style.outlineStyle !== 'none' && parseFloat(style.outlineWidth) > 0) || style.boxShadow !== 'none');
      return {index: index + 1, tag: el.tagName.toLowerCase(), tabindex: el.getAttribute('tabindex'), focus_visible_pseudo: focusVisible,
        visible_indicator: !!indicator, outline_style: style.outlineStyle, outline_width: style.outlineWidth, box_shadow: style.boxShadow !== 'none'};
    }"""
    try:
        with sync_playwright() as playwright:
            browser = playwright.chromium.launch(headless=True)
            viewport_specs = [
                {"width": 320, "height": 800, "label": "small_mobile"},
                {"width": 375, "height": 812, "label": "mobile"},
                {"width": 768, "height": 1024, "label": "tablet"},
                {"width": 1280, "height": 900, "label": "desktop"},
            ]
            viewport_reviews: list[dict[str, Any]] = []
            browser_version = browser.version
            for viewport in viewport_specs:
                context = browser.new_context(
                    java_script_enabled=False, service_workers='block',
                    viewport={"width": viewport["width"], "height": viewport["height"]},
                )
                page = context.new_page()
                page.route('**/*', lambda route: route.abort())
                page.set_content(source, wait_until='domcontentloaded', timeout=10000)
                rendered = page.evaluate(inspect_script)
                layout = page.evaluate("() => ({document_width: document.documentElement.scrollWidth, body_width: document.body ? document.body.scrollWidth : document.documentElement.scrollWidth, viewport_width: innerWidth})")
                focus_steps: list[dict[str, Any]] = []
                seen: set[int] = set()
                for _ in range(min(200, int(rendered['focusableCount']) + 1)):
                    page.keyboard.press('Tab')
                    focus = page.evaluate(focus_script)
                    if not focus:
                        break
                    index = int(focus['index'])
                    if index in seen:
                        break
                    seen.add(index)
                    focus_steps.append(focus)
                viewport_reviews.append({
                    "label": viewport["label"],
                    "viewport": rendered["viewport"],
                    "textRuns": rendered["textRuns"],
                    "focusableCount": rendered["focusableCount"],
                    "focus_order_observed": focus_steps,
                    "document_width": int(layout["document_width"]),
                    "body_width": int(layout["body_width"]),
                    "horizontal_overflow": max(int(layout["document_width"]), int(layout["body_width"])) > int(layout["viewport_width"]) + 1,
                    "linkedStylesheetCount": rendered["linkedStylesheetCount"],
                    "scriptCount": rendered["scriptCount"],
                })
                context.close()
            browser.close()
    except Exception as exc:
        return {
            'schema': 'dio.accessible_publish.rendered_review.v1',
            'source_sha256': source_sha256,
            'runtime_state': 'BROWSER_INSPECTION_FAILED',
            'browser_error_type': type(exc).__name__,
            'issues': [{'check': 'browser_runtime', 'criterion': 'supporting runtime', 'state': 'REVIEW_REQUIRED',
                        'detail': 'The local browser inspection did not complete; no runtime accessibility result is claimed.'}],
            'conformance_claim': 'NONE',
        }
    all_text_runs = [dict(row, viewport=review["label"]) for review in viewport_reviews for row in review["textRuns"]]
    all_focus_steps = [dict(row, viewport=review["label"]) for review in viewport_reviews for row in review["focus_order_observed"]]
    contrast_failures = [row for row in all_text_runs if row['state'] == 'ACTION_REQUIRED']
    contrast_unknown = [row for row in all_text_runs if row['state'] == 'UNKNOWN']
    focus_failures = [row for row in all_focus_steps if not row['visible_indicator']]
    overflow_viewports = [review for review in viewport_reviews if review["horizontal_overflow"]]
    rendered = viewport_reviews[-1] if viewport_reviews else {"focusableCount": 0, "linkedStylesheetCount": 0, "scriptCount": 0, "viewport": {}}
    scripted = _isolated_scripted_review(source, [
        {"width": 320, "height": 800, "label": "small_mobile"},
        {"width": 375, "height": 812, "label": "mobile"},
        {"width": 768, "height": 1024, "label": "tablet"},
        {"width": 1280, "height": 900, "label": "desktop"},
    ])
    scripted_reviews = scripted.get('reviews', [])
    button_interactions = [interaction for row in scripted_reviews
                           for interaction in row.get('button_interaction_review', [])]
    link_interactions = [interaction for row in scripted_reviews
                         for interaction in row.get('link_interaction_review', [])]
    form_interactions = [interaction for row in scripted_reviews
                         for interaction in row.get('form_submission_review', [])]
    changed_button_interactions = sum(
        bool(row.get('text_changed') or row.get('hidden_content_revealed')
             or row.get('aria_expanded_before') != row.get('aria_expanded_after')
             or row.get('aria_pressed_before') != row.get('aria_pressed_after'))
        for row in button_interactions
    )
    scripted_focus_failures = sum(not step.get('visible_indicator', False)
                                  for row in scripted_reviews for step in row.get('focus', []))
    scripted_blocked_count = sum(int(row.get('blocked_request_count', 0)) for row in scripted_reviews)
    scripted_errors = sum(int(row.get('page_error_count', 0)) for row in scripted_reviews)
    scripted_generated_changes = sum(max(0, int(row.get('focusable_count', 0)) - int(static.get('focusableCount', 0)))
                                     for row, static in zip(scripted_reviews, viewport_reviews))
    issues: list[dict[str, Any]] = []
    if contrast_failures:
        issues.append({'check': 'rendered_text_contrast', 'criterion': 'WCAG 2.2 1.4.3', 'state': 'ACTION_REQUIRED',
                       'detail': f"{len(contrast_failures)} rendered text run(s) across {len(viewport_reviews)} viewports fall below the applicable contrast ratio.",
                       'samples': contrast_failures[:25]})
    if contrast_unknown or rendered['linkedStylesheetCount']:
        issues.append({'check': 'rendered_text_contrast', 'criterion': 'WCAG 2.2 1.4.3', 'state': 'REVIEW_REQUIRED',
                       'detail': f"{len(contrast_unknown)} text run(s) could not be resolved; {rendered['linkedStylesheetCount']} linked stylesheet(s) were not loaded. Review browser-computed styling and image/gradient backgrounds.",
                       'samples': contrast_unknown[:25]})
    if overflow_viewports:
        issues.append({'check': 'rendered_horizontal_overflow', 'criterion': 'WCAG 2.2 1.4.10', 'state': 'ACTION_REQUIRED',
                       'detail': 'Horizontal document overflow was detected at: ' + ', '.join(row['label'] for row in overflow_viewports) + '.',
                       'samples': [{key: row[key] for key in ('label', 'document_width', 'body_width', 'viewport')} for row in overflow_viewports]})
    if not rendered['focusableCount']:
        issues.append({'check': 'keyboard_focus_visibility', 'criterion': 'WCAG 2.2 2.4.7', 'state': 'NOT_APPLICABLE',
                       'detail': 'No visible keyboard-focusable controls were found in the static DOM.'})
    elif focus_failures:
        issues.append({'check': 'keyboard_focus_visibility', 'criterion': 'WCAG 2.2 2.4.7', 'state': 'ACTION_REQUIRED',
                       'detail': f"{len(focus_failures)} tab stop(s) had no visible focus indicator in the browser render.",
                       'samples': focus_failures[:25]})
    if scripted.get('state') != 'SCRIPTED_POSTLOAD_DOM_INSPECTED':
        issues.append({'check': 'scripted_dom_review', 'criterion': 'bounded browser runtime', 'state': 'REVIEW_REQUIRED',
                       'detail': 'The isolated scripted DOM pass did not complete; dynamic behavior remains unreviewed.'})
    elif scripted_focus_failures:
        issues.append({'check': 'scripted_keyboard_focus_visibility', 'criterion': 'WCAG 2.2 2.4.7', 'state': 'ACTION_REQUIRED',
                       'detail': f'{scripted_focus_failures} scripted tab stop(s) lacked a visible focus indicator.'})
    if scripted.get('state') == 'SCRIPTED_POSTLOAD_DOM_INSPECTED' and scripted_blocked_count:
        issues.append({'check': 'scripted_interaction_network_attempt', 'criterion': 'bounded network-isolated review', 'state': 'REVIEW_REQUIRED',
                       'detail': f'{scripted_blocked_count} request(s) were blocked during scripted inspection; inspect the interaction and its approved external dependencies.'})
    if scripted.get('state') == 'SCRIPTED_POSTLOAD_DOM_INSPECTED' and any(
            int(row.get('link_count', 0)) > 10 or int(row.get('form_count', 0)) > 10 for row in scripted_reviews):
        issues.append({'check': 'scripted_interaction_review_limit', 'criterion': 'bounded browser runtime', 'state': 'REVIEW_REQUIRED',
                       'detail': 'More than ten links or forms were present in at least one scripted viewport; the interaction review sampled only the first ten of each.'})
    if scripted.get('state') == 'SCRIPTED_POSTLOAD_DOM_INSPECTED' and not button_interactions:
        issues.append({'check': 'scripted_button_interactions', 'criterion': 'bounded user interaction review', 'state': 'NOT_APPLICABLE',
                       'detail': 'No visible enabled type="button" controls were available for the bounded interaction pass.'})
    if scripted_errors:
        issues.append({'check': 'script_runtime_errors', 'criterion': 'scripted DOM review', 'state': 'REVIEW_REQUIRED',
                       'detail': f'{scripted_errors} page error(s) occurred during bounded post-load inspection.'})
    return {
        'schema': 'dio.accessible_publish.rendered_review.v1',
        'source_sha256': source_sha256,
        'runtime_state': 'STATIC_AND_SCRIPTED_DOM_NETWORK_BLOCKED' if scripted.get('state') == 'SCRIPTED_POSTLOAD_DOM_INSPECTED' else 'STATIC_DOM_RENDERED_NETWORK_BLOCKED_SCRIPTS_DISABLED',
        'viewport_coverage': '320, 375, 768 and 1280 CSS pixels',
        'browser': {'engine': 'Chromium', 'version': browser_version},
        'viewport': rendered['viewport'],
        'viewport_count': len(viewport_reviews),
        'viewport_reviews': [{key: row[key] for key in ('label', 'viewport', 'document_width', 'body_width', 'horizontal_overflow', 'focusableCount')} for row in viewport_reviews],
        'horizontal_overflow_viewport_count': len(overflow_viewports),
        'text_run_count': len(all_text_runs),
        'contrast_pass_count': sum(row['state'] == 'PASS' for row in all_text_runs),
        'contrast_failure_count': len(contrast_failures),
        'contrast_unknown_count': len(contrast_unknown),
        'focusable_control_count': rendered['focusableCount'],
        'focus_order_observed': all_focus_steps,
        'focus_failure_count': len(focus_failures),
        'linked_stylesheets_not_loaded': sum(row['linkedStylesheetCount'] for row in viewport_reviews),
        'embedded_scripts_not_executed': sum(row['scriptCount'] for row in viewport_reviews),
        'scripted_runtime_state': scripted.get('state'),
        'script_execution_isolated': True,
        'script_network_blocked': scripted_blocked_count >= 0,
        'scripted_viewport_reviews': [{key: row[key] for key in ('label', 'focusable_count', 'hidden_focusable_count', 'element_count', 'text_char_count', 'script_count', 'external_script_count', 'blocked_request_count', 'page_error_count', 'document_width', 'body_width', 'viewport_width')} for row in scripted_reviews],
        'scripted_focus_failure_count': scripted_focus_failures,
        'scripted_button_interaction_count': len(button_interactions),
        'scripted_button_interaction_change_count': changed_button_interactions,
        'scripted_button_interaction_reviews': button_interactions,
        'scripted_link_interaction_count': len(link_interactions),
        'scripted_link_interaction_reviews': link_interactions,
        'scripted_form_submission_attempt_count': len(form_interactions),
        'scripted_form_submission_event_count': sum(bool(row.get('submit_event_observed')) for row in form_interactions),
        'scripted_form_validation_blocked_count': sum(row.get('valid_before_submit') is False for row in form_interactions),
        'scripted_form_submission_reviews': form_interactions,
        'native_link_navigation_blocked': all(row.get('native_navigation_prevented') is True for row in link_interactions
                                              if row.get('state') == 'CLICKED_NATIVE_NAVIGATION_BLOCKED'),
        'native_form_submission_blocked': all(row.get('native_submission_prevented') is True for row in form_interactions),
        'scripted_focusable_control_count': scripted_reviews[-1].get('focusable_count', 0) if scripted_reviews else None,
        'script_generated_focusable_delta': scripted_generated_changes,
        'scripted_external_script_blocked_count': sum(int(row.get('external_script_count', 0)) for row in scripted_reviews),
        'scripted_page_error_count': scripted_errors,
        'scripted_observation_window_ms': scripted.get('observation_window_ms'),
        'issues': issues,
        'unresolved_areas': ['link destinations and server-side form responses are never followed; only a bounded first-ten interaction sample is exercised', 'custom widgets and user journeys beyond one activation remain unreviewed', 'screen-reader output', 'PDF/UA', 'full WCAG conformance', 'content requiring a human reflow decision'],
        'conformance_claim': 'NONE',
    }


class _HTMLInventory(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.html_lang = ''
        self.title = ''
        self.in_title = False
        self.headings: list[dict[str, Any]] = []
        self._heading: dict[str, Any] | None = None
        self.images: list[dict[str, Any]] = []
        self.tables: list[dict[str, Any]] = []
        self._table: dict[str, Any] | None = None
        self.labels: dict[str, str] = {}
        self._label_stack: list[dict[str, Any]] = []
        self.ids: list[str] = []
        # Descendant text is a deliberately limited static proxy; this does not
        # implement the full Accessible Name and Description Computation.
        self.id_text: dict[str, str] = {}
        self.inputs: list[dict[str, Any]] = []
        self.links: list[dict[str, Any]] = []
        self._link: dict[str, Any] | None = None
        self.buttons: list[dict[str, Any]] = []
        self._button: dict[str, Any] | None = None
        self.focusable_in_aria_hidden: list[dict[str, str]] = []
        self._element_stack: list[tuple[str, bool, str]] = []

    def _record_id(self, value: str) -> None:
        if value.strip():
            self.ids.append(value.strip())

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        a = {str(k).lower(): (v or '') for k, v in attrs}
        inherited_hidden = any(hidden for _, hidden, _ in self._element_stack)
        aria_hidden = inherited_hidden or a.get('aria-hidden', '').strip().casefold() == 'true'
        tabindex = a.get('tabindex', '').strip()
        explicit_tab_stop = bool(re.fullmatch(r'\+?\d+', tabindex))
        is_focusable = ((tag == 'a' and bool(a.get('href'))) or tag in {'button', 'select', 'textarea', 'summary'}
                        or (tag == 'input' and a.get('type', '').casefold() != 'hidden')
                        or (explicit_tab_stop and int(tabindex) >= 0)
                        or (a.get('contenteditable', '').casefold() in {'', 'true'} and 'contenteditable' in a))
        if aria_hidden and is_focusable:
            locator = f"{tag}#{a.get('id')}" if a.get('id') else tag
            self.focusable_in_aria_hidden.append({'element': locator, 'aria_hidden_ancestor': 'true'})
        if tag not in {'area','base','br','col','embed','hr','img','input','link','meta','param','source','track','wbr'}:
            element_id = a.get('id', '').strip()
            self._element_stack.append((tag, aria_hidden, element_id))
            if element_id:
                self.id_text.setdefault(element_id, '')
        self._record_id(a.get('id', ''))
        if tag == 'html': self.html_lang = a.get('lang', '')
        elif tag == 'title': self.in_title = True
        elif re.fullmatch(r'h[1-6]', tag): self._heading = {'level': int(tag[1]), 'text': ''}
        elif tag == 'img': self.images.append({'src': a.get('src', ''), 'alt_present': 'alt' in a, 'alt': a.get('alt', '')})
        elif tag == 'table':
            self._table = {'has_header_cell': False, 'caption': False}
            self.tables.append(self._table)
        elif tag in {'th', 'thead'} and self._table is not None:
            self._table['has_header_cell'] = True
        elif tag == 'caption' and self._table is not None:
            self._table['caption'] = True
        elif tag == 'label':
            self._label_stack.append({'for': a.get('for', '').strip(), 'text': '', 'controls': []})
        elif tag in {'input', 'select', 'textarea'}:
            field = {'id': a.get('id', '').strip(), 'type': a.get('type', '').strip().casefold(),
                     'aria_label': a.get('aria-label', '').strip(),
                     'aria_labelledby': a.get('aria-labelledby', '').strip(),
                     'title': a.get('title', '').strip(), 'value': a.get('value', ''), 'implicit_label': None}
            if self._label_stack:
                self._label_stack[-1]['controls'].append(field)
                field['implicit_label'] = self._label_stack[-1]
            self.inputs.append(field)
        elif tag == 'a': self._link = {'href': a.get('href', ''), 'text': '', 'aria_label': a.get('aria-label', '').strip(), 'aria_labelledby': a.get('aria-labelledby', '').strip()}
        elif tag == 'button': self._button = {'text': '', 'aria_label': a.get('aria-label', '').strip(), 'aria_labelledby': a.get('aria-labelledby', '').strip(), 'title': a.get('title', '').strip()}

    def handle_endtag(self, tag: str) -> None:
        if tag == 'title': self.in_title = False
        elif re.fullmatch(r'h[1-6]', tag) and self._heading is not None:
            self._heading['text'] = self._heading['text'].strip()
            self.headings.append(self._heading); self._heading = None
        elif tag == 'table': self._table = None
        elif tag == 'label' and self._label_stack:
            label = self._label_stack.pop()
            label_text = label['text'].strip()
            if label['for']:
                self.labels[label['for']] = label_text
        elif tag == 'a' and self._link is not None:
            self._link['text'] = self._link['text'].strip(); self.links.append(self._link); self._link = None
        elif tag == 'button' and self._button is not None:
            self._button['text'] = self._button['text'].strip(); self.buttons.append(self._button); self._button = None
        for index in range(len(self._element_stack) - 1, -1, -1):
            if self._element_stack[index][0] == tag:
                del self._element_stack[index:]
                break

    def handle_data(self, data: str) -> None:
        for _, _, element_id in self._element_stack:
            if element_id:
                self.id_text[element_id] += data
        if self.in_title: self.title += data
        if self._heading is not None: self._heading['text'] += data
        for label in self._label_stack: label['text'] += data
        if self._link is not None: self._link['text'] += data
        if self._button is not None: self._button['text'] += data


def inspect_html(source: str, *, declared_language: str = '', decorative_images: set[str] | None = None) -> dict[str, Any]:
    parser = _HTMLInventory(); parser.feed(source); parser.close()
    decorative = decorative_images or set()
    issues: list[dict[str, str]] = []
    id_counts: dict[str, int] = {}
    for value in parser.ids: id_counts[value] = id_counts.get(value, 0) + 1
    duplicate_ids = sorted(value for value, count in id_counts.items() if count > 1)
    if duplicate_ids:
        issues.append({'check':'duplicate_id','criterion':'WCAG 2.2 4.1.2','state':'ACTION_REQUIRED','detail':'Duplicate id values were found: ' + ', '.join(duplicate_ids) + '.'})
    for element in parser.focusable_in_aria_hidden:
        issues.append({'check':'focusable_content_hidden_from_accessibility_tree','criterion':'WCAG 2.2 4.1.2','state':'ACTION_REQUIRED',
                       'detail':f"Focusable element {element['element']} is inside aria-hidden=true content and may remain keyboard reachable while hidden from assistive technology."})

    def labelledby_state(value: str) -> tuple[bool, list[str], bool]:
        refs = [item for item in value.split() if item]
        missing = [item for item in refs if item not in id_counts]
        has_text = any(parser.id_text.get(item, '').strip() for item in refs if item in id_counts)
        return bool(refs) and not missing and has_text, missing, bool(refs) and not has_text
    if not parser.html_lang:
        issues.append({'check':'page_language','criterion':'WCAG 2.2 3.1.1','state':'ACTION_REQUIRED','detail':'The html element has no lang attribute.'})
    elif declared_language and parser.html_lang.casefold() != declared_language.casefold():
        issues.append({'check':'page_language','criterion':'WCAG 2.2 3.1.1','state':'REVIEW_REQUIRED','detail':f"Source declares lang={parser.html_lang}; request declares {declared_language}. Resolve the conflict with the owner."})
    else:
        issues.append({'check':'page_language','criterion':'WCAG 2.2 3.1.1','state':'PASS','detail':f"Page language is programmatically declared as {parser.html_lang}."})
    if not parser.title.strip():
        issues.append({'check':'document_title','criterion':'WCAG 2.2 2.4.2','state':'ACTION_REQUIRED','detail':'The document has no non-empty title element.'})
    else:
        issues.append({'check':'document_title','criterion':'WCAG 2.2 2.4.2','state':'PASS','detail':'A non-empty title element is present.'})
    for image in parser.images:
        src = image['src'] or '(image without src)'
        if not image['alt_present']:
            issues.append({'check':'image_alternative','criterion':'WCAG 2.2 1.1.1','state':'ACTION_REQUIRED','detail':f"Image {src} has no alt attribute."})
        elif image['alt'] == '' and src not in decorative:
            issues.append({'check':'image_alternative','criterion':'WCAG 2.2 1.1.1','state':'REVIEW_REQUIRED','detail':f"Image {src} has empty alt text; confirm that it is decorative."})
        else:
            issues.append({'check':'image_alternative','criterion':'WCAG 2.2 1.1.1','state':'PASS','detail':f"Image {src} has an alt attribute; a human must confirm that its text is equivalent."})
    if not parser.headings:
        issues.append({'check':'heading_structure','criterion':'WCAG 2.2 1.3.1, 2.4.6','state':'REVIEW_REQUIRED','detail':'No semantic heading elements were found.'})
    else:
        levels = [int(x['level']) for x in parser.headings]
        jumps = [(levels[i-1], levels[i]) for i in range(1,len(levels)) if levels[i] > levels[i-1] + 1]
        if not any(level == 1 for level in levels):
            issues.append({'check':'heading_structure','criterion':'WCAG 2.2 1.3.1, 2.4.6','state':'REVIEW_REQUIRED','detail':'No level-one heading was found; confirm the page outline and publication intent.'})
        elif jumps:
            issues.append({'check':'heading_structure','criterion':'WCAG 2.2 1.3.1, 2.4.6','state':'ACTION_REQUIRED','detail':f'Heading levels skip: {jumps}.'})
        else:
            issues.append({'check':'heading_structure','criterion':'WCAG 2.2 1.3.1, 2.4.6','state':'PASS','detail':'Heading elements are present with no detected level jumps.'})
    for index, table in enumerate(parser.tables,1):
        if not table['has_header_cell']:
            issues.append({'check':'table_headers','criterion':'WCAG 2.2 1.3.1','state':'ACTION_REQUIRED','detail':f'Table {index} has no th/thead cell detected.'})
    for field in parser.inputs:
        if field['type'] == 'hidden':
            continue
        labelledby_valid, missing_refs, empty_refs = labelledby_state(field['aria_labelledby'])
        if field['aria_labelledby'] and not labelledby_valid:
            reason = ('missing IDs: ' + ', '.join(missing_refs)) if missing_refs else ('all referenced targets have empty descendant text' if empty_refs else 'no valid ID references')
            issues.append({'check':'aria_labelledby_reference','criterion':'WCAG 2.2 4.1.2','state':'ACTION_REQUIRED','detail':f"Form control {field['id'] or '(no id)'} has aria-labelledby that does not resolve to detected non-empty text ({reason}). Static text check only; verify the computed name with assistive technology."})
        implicit_label = field.get('implicit_label')
        implicit_label_text = str(implicit_label.get('text') or '').strip() if implicit_label else ''
        named = bool(field['aria_label'] or labelledby_valid or field['title']
                      or (field['id'] and parser.labels.get(field['id'], '').strip())
                      or implicit_label_text
                      or (field['type'] in {'button', 'submit', 'reset'} and field.get('value', '').strip()))
        if not named:
            issues.append({'check':'form_control_name','criterion':'WCAG 2.2 3.3.2, 4.1.2','state':'ACTION_REQUIRED','detail':f"Form control {field['id'] or '(no id)'} has no detected label."})
    for button in parser.buttons:
        labelledby_valid, missing_refs, empty_refs = labelledby_state(button.get('aria_labelledby', ''))
        if button.get('aria_labelledby') and not labelledby_valid:
            reason = ('missing IDs: ' + ', '.join(missing_refs)) if missing_refs else ('all referenced targets have empty descendant text' if empty_refs else 'no valid ID references')
            issues.append({'check':'aria_labelledby_reference','criterion':'WCAG 2.2 4.1.2','state':'ACTION_REQUIRED','detail':'Button aria-labelledby does not resolve to detected non-empty text (' + reason + '). Static text check only; verify the computed name with assistive technology.'})
        if not (button['aria_label'] or button['title'] or button['text'] or labelledby_valid):
            issues.append({'check':'button_name','criterion':'WCAG 2.2 4.1.2','state':'ACTION_REQUIRED','detail':'A button has no detected accessible name.'})
    for link in parser.links:
        labelledby_valid, missing_refs, empty_refs = labelledby_state(link.get('aria_labelledby', ''))
        if link.get('aria_labelledby') and not labelledby_valid:
            reason = ('missing IDs: ' + ', '.join(missing_refs)) if missing_refs else ('all referenced targets have empty descendant text' if empty_refs else 'no valid ID references')
            issues.append({'check':'aria_labelledby_reference','criterion':'WCAG 2.2 4.1.2','state':'ACTION_REQUIRED','detail':'Link aria-labelledby does not resolve to detected non-empty text (' + reason + '). Static text check only; verify the computed name with assistive technology.'})
        if not link['aria_label'] and not labelledby_valid and not link['text'].strip():
            issues.append({'check':'link_purpose','criterion':'WCAG 2.2 2.4.4','state':'ACTION_REQUIRED','detail':f"Link to {link['href'] or '(no href)'} has no detected accessible name."})
        elif not link['aria_label'] and not labelledby_valid and link['text'].strip().casefold() in {'here','click here','read more','more'}:
            issues.append({'check':'link_purpose','criterion':'WCAG 2.2 2.4.4','state':'REVIEW_REQUIRED','detail':f"Link text '{link['text']}' may not identify its purpose out of context."})
    for check, criterion, detail in [
        ('text_contrast','WCAG 2.2 1.4.3','Contrast was not calculated because effective styles and backgrounds require browser rendering.'),
        ('keyboard_operation','WCAG 2.2 2.1.1','Keyboard operation and focus order require interactive browser review.'),
        ('screen_reader_review','WCAG 2.2 1.3.1, 4.1.2','Assistive-technology reading order was not exercised by this static source check.'),
    ]:
        issues.append({'check':check,'criterion':criterion,'state':'NOT_EVALUATED','detail':detail})
    return {'html_language':parser.html_lang,'title_present':bool(parser.title.strip()),'title_text':parser.title.strip(),'heading_levels':[x['level'] for x in parser.headings],'image_count':len(parser.images),'table_count':len(parser.tables),'form_control_count':sum(field['type'] != 'hidden' for field in parser.inputs),'hidden_control_count':sum(field['type'] == 'hidden' for field in parser.inputs),'duplicate_ids':duplicate_ids,'focusable_in_aria_hidden':parser.focusable_in_aria_hidden,'issues':issues}


def prepare_html(source: str, *, title: str, primary_language: str, image_descriptions: Mapping[str, str], decorative_images: set[str]) -> tuple[str, list[dict[str, str]]]:
    prepared = source
    changes: list[dict[str, str]] = []
    inventory = inspect_html(source, declared_language=primary_language, decorative_images=decorative_images)
    if not inventory['html_language'] and primary_language:
        def add_lang(match: re.Match[str]) -> str:
            tail = match.group(1)
            return f'<html lang="{html.escape(primary_language, quote=True)}"{tail}>'
        updated, count = re.subn(r'<html\b([^>]*)>', add_lang, prepared, count=1, flags=re.I)
        if count:
            prepared = updated; changes.append({'change':'declared_page_language','detail':f'Added owner-declared lang={primary_language}.'})
    if not inventory['title_present'] and title.strip():
        title_tag = f'<title>{html.escape(title.strip())}</title>'
        if re.search(r'</head\s*>',prepared,re.I):
            prepared = re.sub(r'</head\s*>',title_tag+'</head>',prepared,count=1,flags=re.I)
            changes.append({'change':'document_title','detail':'Inserted owner-supplied title into the head.'})
        elif re.search(r'<html\b[^>]*>',prepared,re.I):
            prepared = re.sub(r'<html\b[^>]*>',lambda m:m.group(0)+'<head>'+title_tag+'</head>',prepared,count=1,flags=re.I)
            changes.append({'change':'document_title','detail':'Inserted owner-supplied title in a new head element.'})
    if image_descriptions or decorative_images:
        def add_alt(match: re.Match[str]) -> str:
            tag = match.group(0)
            src_match = re.search(r'\bsrc\s*=\s*(["\'])(.*?)\1',tag,re.I)
            src = src_match.group(2) if src_match else ''
            existing_alt=re.search(r'\balt\s*=\s*(["\'])(.*?)\1',tag,re.I)
            if existing_alt and existing_alt.group(2).strip(): return tag
            if existing_alt and src not in image_descriptions and src not in decorative_images: return tag
            if src in image_descriptions:
                value = image_descriptions[src]
                changes.append({'change':'image_alternative','detail':f'Added owner-supplied alternative text for {src}.'})
                if existing_alt:
                    return tag[:existing_alt.start(2)] + html.escape(value,quote=True) + tag[existing_alt.end(2):]
                return re.sub(r'\s*/?>$',lambda m:' alt="'+html.escape(value,quote=True)+'"'+(' />' if m.group(0).endswith('/>') else '>'),tag)
            if src in decorative_images:
                changes.append({'change':'decorative_image','detail':f'Added empty alt for owner-designated decorative image {src}.'})
                if existing_alt:
                    return tag[:existing_alt.start(2)] + tag[existing_alt.end(2):]
                return re.sub(r'\s*/?>$',lambda m:' alt=""'+(' />' if m.group(0).endswith('/>') else '>'),tag)
            return tag
        prepared = re.sub(r'<img\b[^>]*>',add_alt,prepared,flags=re.I)
    return prepared,changes


def build_owner_remediation(after: Mapping[str, Any], *, source_path: Path | None) -> dict[str, Any]:
    """Turn unresolved static findings into precise owner actions without guessing content."""
    prompts = {
        'page_language': ('Confirm the primary language using a BCP 47 tag (for example, en-ZA).', 'language_tag'),
        'image_alternative': ('For this image, supply concise text conveying its relevant purpose, or confirm that it is decorative.', 'description_or_decorative'),
        'table_headers': ('Supply the intended column and row header labels, and confirm which cells are headers.', 'header_map'),
        'link_purpose': ('Supply link text that describes the destination and confirm that the target is correct.', 'label_and_target'),
        'aria_labelledby_reference': ('Point aria-labelledby to an element with meaningful text, or provide the correct owner-approved label. The static check only measures descendant text; verify the resulting accessible name with assistive technology.', 'source_reference_or_label'),
    }
    actions: list[dict[str, Any]] = []
    for issue in after.get('issues', []):
        if issue.get('state') not in {'ACTION_REQUIRED', 'REVIEW_REQUIRED'}:
            continue
        check = str(issue.get('check') or '')
        prompt, response_type = prompts.get(check, ('Review this finding and provide the correction or an explicit no-change decision.', 'owner_decision'))
        locator_match = re.search(r'(?:Image\s+)([^ ]+)', str(issue.get('detail') or ''), re.I)
        locator = locator_match.group(1).rstrip('.') if locator_match else check
        actions.append({
            'action_id': f'OWNER-{len(actions)+1:03d}',
            'check': check,
            'criterion': issue.get('criterion'),
            'source_locator': locator,
            'finding': issue.get('detail'),
            'owner_prompt': prompt,
            'expected_response': response_type,
            'state': 'NEEDS_OWNER_INPUT',
            'automated_edit_applied': False,
        })
    unavailable_assets: list[str] = []
    if source_path is not None and source_path.is_file():
        parser = _HTMLInventory(); parser.feed(source_path.read_text(encoding='utf-8')); parser.close()
        for image in parser.images:
            src = str(image.get('src') or '').strip()
            if not src or re.match(r'^(?:[a-z][a-z0-9+.-]*:|//|#)', src, re.I):
                continue
            candidate = (source_path.parent / src).resolve()
            if not candidate.is_relative_to(source_path.parent.resolve()) or not candidate.is_file():
                unavailable_assets.append(src)
    for src in unavailable_assets:
        actions.append({
            'action_id': f'OWNER-{len(actions)+1:03d}',
            'check': 'source_asset_availability',
            'criterion': 'production completeness; not a WCAG conformance determination',
            'source_locator': src,
            'finding': 'The source references an image asset that was not supplied with this packet.',
            'owner_prompt': 'Supply this exact asset or confirm that it should remain an external reference and provide its approved URL.',
            'expected_response': 'asset_file_or_approved_url',
            'state': 'NEEDS_OWNER_INPUT',
            'automated_edit_applied': False,
        })
    return {
        'schema': 'dio.accessible_publish.owner_remediation.v1',
        'source_sha256': after.get('source_sha256'),
        'action_count': len(actions),
        'items': actions,
        'automated_content_guesses': 0,
        'publication_authorized': False,
        'human_review_required': True,
    }


def build_accessible_publish_package(packet: Mapping[str, Any], output_dir: str | Path) -> dict[str, Any]:
    if packet.get('owner_authorized') is not True:
        raise ValueError('owner_authorized=true is required for local source processing')
    case_id = str(packet.get('case_id') or '').strip()
    title = str(packet.get('title') or '').strip()
    if not case_id or not title:
        raise ValueError('case_id and title are required')
    document_title = str(packet.get('document_title') or '').strip()
    source_html = packet.get('source_html')
    source_path = packet.get('source_path')
    if isinstance(source_html,str):
        source_bytes=source_html.encode('utf-8')
    elif source_path:
        path=Path(str(source_path)).expanduser().resolve()
        if not path.is_file() or path.suffix.casefold() not in {'.html','.htm'}:
            raise ValueError('source_path must identify an HTML/HTM file')
        source_bytes=path.read_bytes()
    else:
        raise ValueError('provide source_html or source_path')
    if not source_bytes or len(source_bytes)>MAX_SOURCE_BYTES:
        raise ValueError(f'HTML source must be between 1 byte and {MAX_SOURCE_BYTES} bytes')
    try: source_text=source_bytes.decode('utf-8')
    except UnicodeDecodeError as exc: raise ValueError('HTML input must be UTF-8') from exc
    language=str(packet.get('primary_language') or '').strip()
    if language and not LANG_RE.fullmatch(language):
        raise ValueError('primary_language must be a BCP 47 style language tag such as en or en-ZA')
    descriptions=packet.get('image_descriptions') or {}
    if not isinstance(descriptions,Mapping) or any(not isinstance(k,str) or not isinstance(v,str) or not v.strip() for k,v in descriptions.items()):
        raise ValueError('image_descriptions must map exact image src values to non-empty owner-supplied text')
    decorative=set(str(x) for x in packet.get('decorative_images') or [])
    for src in decorative:
        if src in descriptions: raise ValueError('an image cannot be both decorative and supplied with alternative text')
    out=Path(output_dir).resolve()
    if out.exists() and (not out.is_dir() or any(out.iterdir())):
        raise ValueError('Accessible Publish output directory must be empty')
    out.mkdir(parents=True,exist_ok=True,mode=0o700)
    original_path=out/'SOURCE.html'; original_path.write_bytes(source_bytes)
    prepared,changes=prepare_html(source_text,title=document_title,primary_language=language,image_descriptions=descriptions,decorative_images=decorative)
    prepared_path=out/'PREPARED_REVIEW.html'; prepared_path.write_text(prepared,encoding='utf-8')
    before=inspect_html(source_text,declared_language=language,decorative_images=decorative)
    after=inspect_html(prepared,declared_language=language,decorative_images=decorative)
    if after.get('title_text') and document_title and after['title_text'].strip().casefold() != document_title.casefold():
        after['issues'].append({'check':'document_title','criterion':'WCAG 2.2 2.4.2','state':'REVIEW_REQUIRED','detail':f"Existing title '{after['title_text']}' differs from the owner-requested title '{document_title}'."})
    rendered=inspect_rendered_html(prepared,source_sha256=sha256(prepared.encode('utf-8')))
    rendered_path=out/'RENDERED_ACCESSIBILITY_REVIEW.json'
    rendered_path.write_text(json.dumps(rendered,ensure_ascii=False,indent=2)+'\n')
    report_issues=[*after['issues'],*rendered.get('issues',[])]
    report={'schema':'dio.accessible_publish.review.v1','case_id':case_id,'title':title,'standard_reference':{'name':'Web Content Accessibility Guidelines (WCAG) 2.2','publisher':'W3C','recommendation_url':W3C_SOURCE},'source_sha256':sha256(source_bytes),'prepared_html_sha256':sha256(prepared.encode('utf-8')),'before':before,'after':after,'rendered_browser_review':rendered,'owner_supplied_repairs':changes,'preparation_scope':'Static HTML inventory plus isolated Chromium checks. A disposable worker executes bounded button, link and form interactions in separate network-blocked browser contexts and prevents native navigation and submission.','unresolved_review_areas':['Link destinations and server-side form responses are not followed; interaction sampling is capped at ten links and ten forms per viewport','Custom widgets and broader user journeys','Screen-reader reading order and meaning','Equivalent and context-appropriate image descriptions','Content clarity, cognitive accessibility, language quality','PDF accessibility or PDF/UA tagging','Full WCAG conformance'],'conformance_claim':'NONE','release_authorized':False,'external_publication':False,'human_review_required':True,'commercial_validation':'UNPROVED'}
    report_path=out/'ACCESSIBILITY_REVIEW.json'; report_path.write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n')
    remediation_input={**after,'issues':report_issues}
    remediation=build_owner_remediation(remediation_input,source_path=Path(str(packet['source_path'])).expanduser().resolve() if packet.get('source_path') else None)
    remediation['source_sha256']=sha256(source_bytes)
    remediation_path=out/'OWNER_REMEDIATION_REQUEST.json'; remediation_path.write_text(json.dumps(remediation,ensure_ascii=False,indent=2)+'\n')
    remediation_md=['# Accessible Publish · owner remediation request','','This checklist turns detected source issues into concrete questions. It does not guess image meaning, declare conformance, or authorize release.','']
    for item in remediation['items']:
        remediation_md.extend([f"## {item['action_id']} · {item['source_locator']}", '', f"**Finding:** {item['finding']}", '', f"**Owner action:** {item['owner_prompt']}", '', f"**Reply format:** `{item['expected_response']}`", '', '**State:** Needs owner input.', ''])
    if not remediation['items']:
        remediation_md.extend(['No unresolved owner inputs were found by the supported static checks.', ''])
    remediation_md.extend(['Publication remains held pending owner and accessibility review.'])
    remediation_md_path=out/'OWNER_REMEDIATION_REQUEST.md'; remediation_md_path.write_text('\n'.join(remediation_md)+'\n',encoding='utf-8')
    rows=''.join(f"<tr><td>{html.escape(i['check'])}</td><td>{html.escape(i['state'])}</td><td>{html.escape(i['detail'])}</td></tr>" for i in report_issues)
    report_html=f'''<!doctype html><html lang="en"><head><meta charset="utf-8"><title>{html.escape(title)} · accessibility review</title><meta name="viewport" content="width=device-width,initial-scale=1"><style>body{{font:16px/1.5 system-ui,sans-serif;max-width:1100px;margin:2rem auto;padding:0 1rem;color:#1f2937}}table{{border-collapse:collapse;width:100%}}th,td{{border:1px solid #ccd3dc;padding:.6rem;text-align:left}}th{{background:#eef2f6}}.gate{{padding:1rem;background:#fff4d6;border-inline-start:5px solid #b57600}}</style></head><body><h1>{html.escape(title)} · accessibility review</h1><p class="gate"><strong>Human review required. No WCAG conformance or publication approval is claimed.</strong></p><p>Source SHA-256: <code>{sha256(source_bytes)}</code></p><p>Local browser result: {html.escape(str(rendered.get('runtime_state') or 'unknown'))}; {rendered.get('contrast_failure_count', '—')} contrast finding(s), {rendered.get('focus_failure_count', '—')} keyboard focus finding(s). <a href="RENDERED_ACCESSIBILITY_REVIEW.json">Browser review details</a>.</p><table><thead><tr><th>Check</th><th>State</th><th>Finding</th></tr></thead><tbody>{rows}</tbody></table><h2>Preparation changes</h2><ul>{''.join(f'<li>{html.escape(c["detail"])}</li>' for c in changes) or '<li>No automated changes were applied.</li>'}</ul></body></html>'''
    review_path=out/'ACCESSIBILITY_REVIEW.html'; review_path.write_text(report_html,encoding='utf-8')
    artifacts=[]
    for path in (original_path,prepared_path,report_path,rendered_path,review_path,remediation_path,remediation_md_path):
        artifacts.append({'path':path.name,'sha256':sha256(path.read_bytes()),'bytes':path.stat().st_size})
    receipt={'schema':'dio.accessible_publish.receipt.v1','case_id':case_id,'source_sha256':sha256(source_bytes),'prepared_sha256':sha256(prepared.encode('utf-8')),'rendered_review':{'path':rendered_path.name,'sha256':sha256(rendered_path.read_bytes()),'runtime_state':rendered.get('runtime_state')},'artifacts':artifacts,'owner_remediation_request':{'path':remediation_path.name,'sha256':sha256(remediation_path.read_bytes()),'action_count':remediation['action_count']},'preparation_changes':changes,'review_state':'HELD_FOR_HUMAN_ACCESSIBILITY_REVIEW','conformance_claim':'NONE','release_authorized':False,'external_publication':False,'human_review_required':True,'authority_created':False,'external_effects':False,'commercial_validation':'UNPROVED'}
    (out/'ACCESSIBLE_PUBLISH_RECEIPT.json').write_text(json.dumps(receipt,ensure_ascii=False,indent=2)+'\n')
    return receipt
