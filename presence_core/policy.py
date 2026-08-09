from __future__ import annotations
PUBLIC_ALLOWED={'help','general_info','product_info','pricing_info','intake_request','status_request','translation_info','formatting_info','attachment_received','unknown'}
OPERATOR_ALLOWED=PUBLIC_ALLOWED|{'operator_summary','campaign_summary','revenue_summary','mail_summary','job_summary','needs_you'}

def authorize(role:str,intent:str)->tuple[bool,str]:
    allowed=OPERATOR_ALLOWED if role=='operator' else PUBLIC_ALLOWED
    if intent not in allowed: return False,'intent_not_allowed_for_role'
    if role!='operator' and intent in {'operator_summary','campaign_summary','revenue_summary','mail_summary','job_summary','needs_you'}: return False,'operator_authority_required'
    return True,'allowed'
