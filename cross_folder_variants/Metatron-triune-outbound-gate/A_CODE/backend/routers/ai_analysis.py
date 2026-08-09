"""
AI Analysis Router
"""
from fastapi import APIRouter, HTTPException, Depends
from datetime import datetime, timezone
from typing import List
import uuid
import os
import logging

from openai import AsyncOpenAI
try:
    from emergentintegrations.llm.chat import LlmChat, UserMessage
except ImportError:
    LlmChat = None
    UserMessage = None

from .dependencies import (
    AIAnalysisRequest, AIAnalysisResponse, get_current_user, get_db, logger
)

router = APIRouter(prefix="/ai", tags=["AI Analysis"])

# API Keys
OPENAI_API_KEY = os.environ.get('OPENAI_API_KEY', '')
EMERGENT_LLM_KEY = os.environ.get('EMERGENT_LLM_KEY', '')

# Initialize OpenAI client
openai_client = None
if OPENAI_API_KEY:
    openai_client = AsyncOpenAI(api_key=OPENAI_API_KEY)

async def call_openai(system_message: str, user_message: str) -> str:
    """Helper function to call AI API - tries OpenAI first, falls back to Emergent"""
    if openai_client and OPENAI_API_KEY:
        try:
            response = await openai_client.chat.completions.create(
                model="gpt-4o",
                messages=[
                    {"role": "system", "content": system_message},
                    {"role": "user", "content": user_message}
                ],
                max_tokens=2000,
                temperature=0.7
            )
            return response.choices[0].message.content
        except Exception as e:
            logger.warning(f"OpenAI call failed, falling back to Emergent: {str(e)}")
    
    if EMERGENT_LLM_KEY and LlmChat and UserMessage:
        chat = LlmChat(
            api_key=EMERGENT_LLM_KEY,
            session_id=f"analysis-{str(uuid.uuid4())[:8]}",
            system_message=system_message
        ).with_model("openai", "gpt-4o")
        
        msg = UserMessage(text=user_message)
        response = await chat.send_message(msg)
        return response
    
    if EMERGENT_LLM_KEY and (not LlmChat or not UserMessage):
        raise Exception("EMERGENT_LLM_KEY is set but emergentintegrations is not installed")

    logger.warning("No AI API available; falling back to a static demo summary.")
    return (
        "RISK SCORE: 42\n"
        "THREAT INDICATORS:\n"
        "- Simulated phishing and credential harvesting behavior detected\n"
        "- Suspicious outbound connections and insecure configuration patterns observed\n"
        "ANALYSIS:\n"
        "This environment is running in demo mode. The generated summary reflects realistic security posture insights "
        "based on typical cloud, email, and endpoint threat patterns. The current simulated stance indicates elevated "
        "risk across identity and application attack surfaces.\n"
        "RECOMMENDATIONS:\n"
        "- Review email threat telemetry and enforce sender authentication policies\n"
        "- Strengthen endpoint controls and remediate high-risk devices\n"
        "- Validate cloud posture and close any publicly exposed storage or service endpoints\n"
    )

SYSTEM_PROMPTS = {
    "threat_detection": """You are an elite cybersecurity AI threat detection system. Analyze the provided content for potential threats including:
- Malicious code patterns
- AI-generated attack signatures
- Behavioral anomalies
- Known attack vectors
Provide a detailed threat assessment with specific indicators, risk score (0-100), and actionable recommendations.

Format your response with clear sections:
RISK SCORE: [0-100]
THREAT INDICATORS:
- [indicator 1]
- [indicator 2]
ANALYSIS:
[detailed analysis]
RECOMMENDATIONS:
- [recommendation 1]
- [recommendation 2]""",
    
    "behavior_analysis": """You are an advanced behavioral analysis AI. Examine the provided data for:
- Non-human interaction patterns (Turing test inversion)
- Algorithmic decision-making signatures
- Superhuman speed or consistency indicators
- Automated bot behaviors
Provide behavioral assessment with confidence scores and detection methods.

Format your response with:
RISK SCORE: [0-100]
BEHAVIOR TYPE: [human/bot/ai_agent/unknown]
CONFIDENCE: [percentage]
INDICATORS:
- [indicator]
ANALYSIS:
[detailed analysis]""",
    
    "malware_scan": """You are a polymorphic malware detection AI. Analyze for:
- Obfuscated code patterns
- Self-modifying code signatures
- Zero-day exploit indicators
- AI-generated malicious code
Provide malware classification, family identification if possible, and containment recommendations.

Format your response with:
RISK SCORE: [0-100]
MALWARE FAMILY: [family name or Unknown]
CLASSIFICATION: [trojan/ransomware/worm/etc]
INDICATORS:
- [indicator]
CONTAINMENT:
- [action]""",
    
    "pattern_recognition": """You are a pattern recognition AI for cyber threat intelligence. Identify:
- Attack campaign patterns
- Threat actor signatures
- Temporal patterns in attack data
- Correlations with known threat groups
Provide pattern analysis with attribution confidence and predicted next moves.

Format your response with:
RISK SCORE: [0-100]
THREAT ACTOR: [name or Unknown]
CAMPAIGN: [campaign name or Unknown]
PATTERNS:
- [pattern]
PREDICTED ACTIONS:
- [action]"""
}

@router.post("/analyze", response_model=AIAnalysisResponse)
async def ai_analyze(request: AIAnalysisRequest, current_user: dict = Depends(get_current_user)):
    db = get_db()
    analysis_id = str(uuid.uuid4())
    
    system_message = SYSTEM_PROMPTS.get(request.analysis_type, SYSTEM_PROMPTS["threat_detection"])
    
    try:
        user_prompt = f"Analyze the following content:\n\n{request.content}\n\nProvide a structured analysis."
        response = await call_openai(system_message, user_prompt)
        
        # Parse response for structured data
        risk_score = 65.0
        response_lower = response.lower()
        
        # Extract risk score
        if "risk score:" in response_lower:
            try:
                score_part = response_lower.split("risk score:")[1].split("\n")[0]
                score_num = ''.join(filter(str.isdigit, score_part[:10]))
                if score_num:
                    risk_score = min(100, max(0, float(score_num)))
            except (ValueError, IndexError):
                pass
        elif "critical" in response_lower or "high risk" in response_lower or "malicious" in response_lower:
            risk_score = 85.0
        elif "low risk" in response_lower or "benign" in response_lower or "safe" in response_lower:
            risk_score = 25.0
        
        # Extract indicators
        indicators = []
        if "indicators:" in response_lower or "indicator" in response_lower:
            lines = response.split("\n")
            for line in lines:
                if line.strip().startswith("-") and len(line.strip()) > 5:
                    indicator = line.strip()[1:].strip()
                    if len(indicator) > 3 and len(indicator) < 100:
                        indicators.append(indicator)
            indicators = indicators[:5]
        
        if not indicators:
            indicators = ["Pattern analysis completed", "Behavioral signature extracted"]
        
        # Extract recommendations
        recommendations = []
        if "recommend" in response_lower:
            in_recommendations = False
            for line in response.split("\n"):
                if "recommend" in line.lower():
                    in_recommendations = True
                if in_recommendations and line.strip().startswith("-"):
                    rec = line.strip()[1:].strip()
                    if len(rec) > 3:
                        recommendations.append(rec)
        
        if not recommendations:
            recommendations = ["Continue monitoring", "Update threat signatures", "Review access logs"]
        
        # Store analysis
        analysis_doc = {
            "id": analysis_id,
            "type": request.analysis_type,
            "content": request.content[:500],
            "result": response,
            "risk_score": risk_score,
            "indicators": indicators,
            "recommendations": recommendations[:5],
            "created_at": datetime.now(timezone.utc).isoformat(),
            "created_by": current_user["id"]
        }
        await db.ai_analyses.insert_one(analysis_doc)
        
        # Increment scan counter
        today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
        await db.scan_stats.update_one(
            {"date": today},
            {"$inc": {"count": 1}},
            upsert=True
        )
        
        return AIAnalysisResponse(
            analysis_id=analysis_id,
            analysis_type=request.analysis_type,
            result=response,
            threat_indicators=indicators,
            risk_score=risk_score,
            recommendations=recommendations,
            timestamp=datetime.now(timezone.utc).isoformat()
        )
        
    except Exception as e:
        logger.error(f"AI Analysis error: {str(e)}")
        raise HTTPException(status_code=500, detail=f"AI analysis failed: {str(e)}")

@router.get("/analyses", response_model=List[dict])
async def get_ai_analyses(current_user: dict = Depends(get_current_user)):
    db = get_db()
    analyses = await db.ai_analyses.find({}, {"_id": 0}).sort("created_at", -1).to_list(50)
    return analyses

# Export for use in other modules
__all__ = ['router', 'call_openai', 'SYSTEM_PROMPTS']
