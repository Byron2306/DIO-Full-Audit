"""Disposable Chromium worker for bounded post-load DOM inspection."""
from __future__ import annotations

import json
import sys


def main() -> int:
    request = json.load(sys.stdin)
    source = request["source"]
    specs = request["viewports"]
    try:
        from playwright.sync_api import sync_playwright
    except ImportError:
        print(json.dumps({"state": "SCRIPTED_BROWSER_UNAVAILABLE", "reviews": []}))
        return 0
    reviews = []
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        version = browser.version
        for spec in specs:
            context = browser.new_context(java_script_enabled=True, service_workers="block",
                                          accept_downloads=False,
                                          viewport={"width": spec["width"], "height": spec["height"]})
            page = context.new_page()
            blocked = {"count": 0}
            page.on("request", lambda req: blocked.__setitem__("count", blocked["count"] + 1))
            page.route("**/*", lambda route: route.abort())
            errors = []
            page.on("pageerror", lambda exc: errors.append(type(exc).__name__))
            page.set_content(source, wait_until="domcontentloaded", timeout=8000)
            page.wait_for_timeout(200)
            result = page.evaluate("""() => {
              const visible = el => { const s=getComputedStyle(el); return !!el.getClientRects().length && s.display!=='none' && s.visibility!=='hidden' && Number(s.opacity||1)>0; };
              const controls=[...document.querySelectorAll('a[href],button,input,select,textarea,summary,[tabindex]')].filter(e=>!e.disabled&&e.tabIndex>=0&&visible(e));
              // Limit interaction to ordinary non-submit buttons. Each click
              // runs in this disposable, network-blocked page context.
              const buttons=[...document.querySelectorAll('button[type="button"]')].filter(e=>!e.disabled&&visible(e)).slice(0,10);
              const interaction=[];
              for(const button of buttons){
                const beforeText=(document.body?.innerText||'').slice(0,12000);
                const beforeExpanded=button.getAttribute('aria-expanded');
                const beforePressed=button.getAttribute('aria-pressed');
                const controlledIds=(button.getAttribute('aria-controls')||'').split(' ').filter(Boolean);
                const label=(button.innerText||button.getAttribute('aria-label')||'').trim().slice(0,160);
                button.click();
                const afterText=(document.body?.innerText||'').slice(0,12000);
                interaction.push({label, text_changed:beforeText!==afterText,
                  aria_expanded_before:beforeExpanded,aria_expanded_after:button.getAttribute('aria-expanded'),
                  aria_pressed_before:beforePressed,aria_pressed_after:button.getAttribute('aria-pressed'),
                  controlled_content_visible:controlledIds.length ? controlledIds.some(id=>{const e=document.getElementById(id);return !!e&&visible(e);}) : null});
              }
              const linkEvents=[];
              document.addEventListener('click',event=>{
                const anchor=event.target?.closest?.('a[href]');
                if(!anchor)return;
                linkEvents.push({anchor,prevented_by_page:event.defaultPrevented});
                event.preventDefault();
              },false);
              const links=[...document.querySelectorAll('a[href]')].filter(visible).slice(0,10);
              const linkInteraction=[];
              for(const anchor of links){
                const beforeText=(document.body?.innerText||'').slice(0,12000), beforeUrl=location.href;
                const href=anchor.getAttribute('href')||'';
                const label=(anchor.innerText||anchor.getAttribute('aria-label')||'').trim().slice(0,160);
                if(!/^(?:https?:|mailto:|tel:|\/|#|\.)/i.test(href)){
                  linkInteraction.push({label,href_class:'unsupported',state:'SKIPPED_UNSUPPORTED_SCHEME'});continue;
                }
                const eventCount=linkEvents.length;
                anchor.click();
                const afterText=(document.body?.innerText||'').slice(0,12000), observed=linkEvents[eventCount];
                const hrefClass=/^(?:https?:)?\/\//i.test(href)?'external_http':/^mailto:/i.test(href)?'mailto':/^tel:/i.test(href)?'tel':href.startsWith('#')?'same_document_anchor':href.startsWith('/')?'root_relative':'relative';
                linkInteraction.push({label,href_class:hrefClass,state:'CLICKED_NATIVE_NAVIGATION_BLOCKED',
                  text_changed:beforeText!==afterText,location_changed:location.href!==beforeUrl,
                  prevented_by_page:observed?.prevented_by_page??null,native_navigation_prevented:true});
              }
              const submitEvents=[];
              document.addEventListener('submit',event=>{
                const form=event.target;
                submitEvents.push({form,prevented_by_page:event.defaultPrevented,
                  submitter_tag:event.submitter?.tagName?.toLowerCase()||null});
                event.preventDefault();
              },false);
              const forms=[...document.querySelectorAll('form')].filter(visible).slice(0,10);
              const formInteraction=[];
              for(const form of forms){
                const eventCount=submitEvents.length;
                let validBefore=null,requestState='REQUESTED';
                try{validBefore=form.checkValidity();form.requestSubmit();}
                catch(error){requestState='REQUEST_FAILED:'+error.name;}
                const observed=submitEvents[eventCount];
                formInteraction.push({id:form.id||null,method:(form.method||'get').toLowerCase(),
                  action_present:!!form.getAttribute('action'),valid_before_submit:validBefore,
                  submit_event_observed:!!observed,prevented_by_page:observed?.prevented_by_page??null,
                  native_submission_prevented:true,request_state:requestState});
              }
              const hiddenFocusables=[...document.querySelectorAll('[aria-hidden=true] a[href],[aria-hidden=true] button,[aria-hidden=true] input,[aria-hidden=true] select,[aria-hidden=true] textarea,[aria-hidden=true] [tabindex]')].filter(e=>!e.disabled&&e.tabIndex>=0);
              const focus=[]; for(let i=0;i<Math.min(200,controls.length);i++){ controls[i].focus(); const e=document.activeElement, s=getComputedStyle(e); const v=e.matches(':focus-visible')&&((s.outlineStyle!=='none'&&parseFloat(s.outlineWidth)>0)||s.boxShadow!=='none'); focus.push({index:i+1,visible_indicator:!!v}); }
              return {focusable_count:controls.length,hidden_focusable_count:hiddenFocusables.length,element_count:document.querySelectorAll('body *').length,
                text_char_count:(document.body?.innerText||'').length,script_count:document.querySelectorAll('script').length,
                external_script_count:document.querySelectorAll('script[src]').length,focus,button_interaction_review:interaction,
                link_interaction_review:linkInteraction,link_count:document.querySelectorAll('a[href]').length,
                form_submission_review:formInteraction,form_count:document.querySelectorAll('form').length,
                document_width:document.documentElement.scrollWidth,
                body_width:document.body?.scrollWidth||document.documentElement.scrollWidth,viewport_width:innerWidth};
            }""")
            result.update({"label": spec["label"], "blocked_request_count": blocked["count"],
                           "page_error_count": len(errors), "page_error_types": errors[:10]})
            reviews.append(result)
            context.close()
        browser.close()
    print(json.dumps({"state": "SCRIPTED_POSTLOAD_DOM_INSPECTED", "browser_version": version,
                      "observation_window_ms": 200, "reviews": reviews}, separators=(",", ":")))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
