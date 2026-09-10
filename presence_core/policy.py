from __future__ import annotations
PUBLIC_ALLOWED={'help','general_info','product_info','pricing_info','intake_request','status_request','translation_info','formatting_info','attachment_received','unknown'}
CAPITAL_OPERATOR_ALLOWED={
    'capital_priority','capital_explain','capital_draft','capital_grants','capital_patronage',
    'capital_find_type','capital_find_domain','capital_find_geography','capital_deadlines',
    'capital_rank_move','capital_missing_proof',
}
OPERATOR_ALLOWED=PUBLIC_ALLOWED|{'operator_summary','campaign_summary','revenue_summary','mail_summary','job_summary','needs_you'}|CAPITAL_OPERATOR_ALLOWED

def authorize(role:str,intent:str)->tuple[bool,str]:
    allowed=OPERATOR_ALLOWED if role=='operator' else PUBLIC_ALLOWED
    if intent not in allowed: return False,'intent_not_allowed_for_role'
    if role!='operator' and intent in {'operator_summary','campaign_summary','revenue_summary','mail_summary','job_summary','needs_you'}|CAPITAL_OPERATOR_ALLOWED: return False,'operator_authority_required'
    return True,'allowed'
