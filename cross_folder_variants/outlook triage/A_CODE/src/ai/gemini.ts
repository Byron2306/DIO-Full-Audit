import { GoogleGenAI, Type } from "@google/genai";
import { loadProfile, buildProfileContext, loadContacts, getRecentMemory, searchMemory } from "../knowledge/profile.js";

const ai = new GoogleGenAI({ apiKey: process.env.GEMINI_API_KEY || "" });

export interface EmailClassification {
  folder: string;
  reason: string;
  priority: "High" | "Medium" | "Low";
  suggestedAction: string;
  senderRelationship: string;
}

export interface AgentDecision {
  action: string;
  target?: string;
  params?: Record<string, any>;
  reasoning: string;
}

export interface ContextualAnalysis {
  situation: string;
  urgency: "immediate" | "today" | "this_week" | "when_possible" | "no_action";
  relatedThreads: string[];
  suggestedResponse: string;
  backgroundContext: string;
}

async function getPersonalContext(): Promise<string> {
  const profile = await loadProfile();
  const profileCtx = buildProfileContext(profile);
  if (!profileCtx) return "";

  const contacts = await loadContacts();
  const contactsCtx = contacts.length > 0
    ? "\nKnown Contacts:\n" + contacts.slice(0, 20).map((c) => `- ${c.name} (${c.email}): ${c.relationship} — ${c.context}`).join("\n")
    : "";

  const recentMemory = await getRecentMemory(undefined, 10);
  const memoryCtx = recentMemory.length > 0
    ? "\nRecent Memory/Context:\n" + recentMemory.map((m) => `- [${m.type}] ${m.summary}`).join("\n")
    : "";

  return `\n--- PERSONAL CONTEXT (use this to personalize all responses) ---\n${profileCtx}${contactsCtx}${memoryCtx}\n--- END PERSONAL CONTEXT ---\n`;
}

export async function classifyEmail(
  from: string,
  subject: string,
  bodyPreview: string,
  customFolders?: string[]
): Promise<EmailClassification> {
  const personalCtx = await getPersonalContext();
  const profile = await loadProfile();
  const contact = (await loadContacts()).find(
    (c) => from.toLowerCase().includes(c.email.toLowerCase()) || from.toLowerCase().includes(c.name.toLowerCase())
  );

  const folderList = (customFolders && customFolders.length > 0 ? customFolders : profile.customFolders.length > 0 ? profile.customFolders : [
    "Inbox", "Students_Queries", "Admin_Management", "Deadlines_Alerts", "Other_To_Review", "Events_Training",
  ]).map((f) => `- ${f}`).join("\n");

  const contactCtx = contact
    ? `\nKnown sender: ${contact.name} — ${contact.relationship}. Context: ${contact.context}`
    : "";

  const prompt = `
    ${personalCtx}
    ${contactCtx}

    Classify this email into one of these folders:
    ${folderList}

    Consider the sender's relationship to the user, the urgency, and how this fits
    into the user's current work and projects.

    Email Details:
    From: ${from}
    Subject: ${subject}
    Preview: ${bodyPreview}

    Return JSON with: folder, reason, priority (High/Medium/Low), suggestedAction, senderRelationship.
  `;

  try {
    const response = await ai.models.generateContent({
      model: "gemini-2.0-flash",
      contents: prompt,
      config: {
        responseMimeType: "application/json",
        responseSchema: {
          type: Type.OBJECT,
          properties: {
            folder: { type: Type.STRING },
            reason: { type: Type.STRING },
            priority: { type: Type.STRING, enum: ["High", "Medium", "Low"] },
            suggestedAction: { type: Type.STRING },
            senderRelationship: { type: Type.STRING },
          },
          required: ["folder", "reason", "priority", "suggestedAction", "senderRelationship"],
        },
      },
    });
    return JSON.parse(response.text || "{}");
  } catch (error) {
    console.error("Classification error:", error);
    return {
      folder: "Other_To_Review",
      reason: "Error during classification",
      priority: "Low",
      suggestedAction: "Review manually",
      senderRelationship: "unknown",
    };
  }
}

export async function generateDraft(
  from: string,
  subject: string,
  bodyContent: string
): Promise<string> {
  const personalCtx = await getPersonalContext();
  const profile = await loadProfile();
  const contact = (await loadContacts()).find(
    (c) => from.toLowerCase().includes(c.email.toLowerCase()) || from.toLowerCase().includes(c.name.toLowerCase())
  );

  const relatedMemory = await searchMemory(subject, 5);
  const memoryCtx = relatedMemory.length > 0
    ? "\nRelated previous interactions:\n" + relatedMemory.map((m) => `- ${m.summary}`).join("\n")
    : "";

  const contactNote = contact
    ? `\nYou know this person: ${contact.name} — ${contact.relationship}. ${contact.notes}`
    : "";

  const prompt = `
    ${personalCtx}
    ${contactNote}
    ${memoryCtx}

    Write a reply to this email AS the user described in the personal context above.
    Match their communication style and tone (${profile.communication.tone || "professional"}).
    End with "${profile.communication.signOff || "Kind regards"}".

    Rules:
    - Be direct and substantive. No filler.
    - NO placeholder brackets like [Date] or [Name].
    - Reference specific details from the original email.
    - If there's relevant context from previous interactions, weave it in naturally.
    - This is a DRAFT. The human will review before sending.

    Email to reply to:
    From: ${from}
    Subject: ${subject}
    Content: ${bodyContent}
  `;

  try {
    const response = await ai.models.generateContent({
      model: "gemini-2.0-flash",
      contents: prompt,
      config: { temperature: 0.3 },
    });
    return response.text || "Could not generate draft.";
  } catch (error) {
    console.error("Draft generation error:", error);
    return "Error generating draft.";
  }
}

export async function analyzeEmailContext(
  from: string,
  subject: string,
  body: string
): Promise<ContextualAnalysis> {
  const personalCtx = await getPersonalContext();
  const relatedMemory = await searchMemory(subject, 5);
  const senderMemory = await searchMemory(from, 5);
  const allRelated = [...relatedMemory, ...senderMemory]
    .filter((m, i, arr) => arr.findIndex((a) => a.id === m.id) === i)
    .slice(0, 8);

  const memoryCtx = allRelated.length > 0
    ? "\nRelated history:\n" + allRelated.map((m) => `- [${m.timestamp.split("T")[0]}] ${m.summary}`).join("\n")
    : "";

  const prompt = `
    ${personalCtx}
    ${memoryCtx}

    Deeply analyze this email in the context of the user's work, relationships, and history.

    Email:
    From: ${from}
    Subject: ${subject}
    Body: ${body}

    Provide:
    - situation: What is this about and how does it relate to the user's work?
    - urgency: How quickly does this need attention? (immediate/today/this_week/when_possible/no_action)
    - relatedThreads: What past conversations or projects might this connect to?
    - suggestedResponse: What should the user do about this?
    - backgroundContext: Any relevant background the user should keep in mind
  `;

  try {
    const response = await ai.models.generateContent({
      model: "gemini-2.0-flash",
      contents: prompt,
      config: {
        responseMimeType: "application/json",
        responseSchema: {
          type: Type.OBJECT,
          properties: {
            situation: { type: Type.STRING },
            urgency: { type: Type.STRING, enum: ["immediate", "today", "this_week", "when_possible", "no_action"] },
            relatedThreads: { type: Type.ARRAY, items: { type: Type.STRING } },
            suggestedResponse: { type: Type.STRING },
            backgroundContext: { type: Type.STRING },
          },
          required: ["situation", "urgency", "relatedThreads", "suggestedResponse", "backgroundContext"],
        },
      },
    });
    return JSON.parse(response.text || "{}");
  } catch (error) {
    console.error("Context analysis error:", error);
    return {
      situation: "Could not analyze",
      urgency: "when_possible",
      relatedThreads: [],
      suggestedResponse: "Review manually",
      backgroundContext: "",
    };
  }
}

export async function summarizeEmails(
  emails: { from: string; subject: string; preview: string }[]
): Promise<string> {
  const personalCtx = await getPersonalContext();
  const emailList = emails
    .map((e, i) => `${i + 1}. From: ${e.from} | Subject: ${e.subject} | Preview: ${e.preview}`)
    .join("\n");

  const prompt = `
    ${personalCtx}

    Summarize these emails from the user's perspective. Consider their role, relationships,
    and current projects when assessing priority.

    For each email provide:
    - Priority (High/Medium/Low) based on the user's actual work
    - One-line contextual summary (not just the subject, but what it MEANS for the user)
    - Whether it needs a reply and how urgently
    - Who the sender is in relation to the user (if recognizable)

    Emails:
    ${emailList}

    End with a brief "Action Plan" — the 2-3 most important things the user should do first.
  `;

  try {
    const response = await ai.models.generateContent({
      model: "gemini-2.0-flash",
      contents: prompt,
    });
    return response.text || "Could not summarize.";
  } catch (error) {
    console.error("Summarization error:", error);
    return "Error summarizing emails.";
  }
}

export async function analyzeDocumentForFilling(
  documentContent: string,
  context: string
): Promise<{ fields: { name: string; suggestedValue: string; confidence: string }[]; notes: string }> {
  const personalCtx = await getPersonalContext();

  const prompt = `
    ${personalCtx}

    You are helping the user fill out a document/form. Using the personal context above,
    suggest values for each field you can identify.

    Document content:
    ${documentContent}

    Additional context:
    ${context}

    For each field, provide the field name, a suggested value (from the user's profile
    or reasonable inference), and your confidence level (high/medium/low).
    Also provide any notes about fields you couldn't fill or that need the user's input.
  `;

  try {
    const response = await ai.models.generateContent({
      model: "gemini-2.0-flash",
      contents: prompt,
      config: {
        responseMimeType: "application/json",
        responseSchema: {
          type: Type.OBJECT,
          properties: {
            fields: {
              type: Type.ARRAY,
              items: {
                type: Type.OBJECT,
                properties: {
                  name: { type: Type.STRING },
                  suggestedValue: { type: Type.STRING },
                  confidence: { type: Type.STRING },
                },
                required: ["name", "suggestedValue", "confidence"],
              },
            },
            notes: { type: Type.STRING },
          },
          required: ["fields", "notes"],
        },
      },
    });
    return JSON.parse(response.text || '{"fields":[],"notes":"Parse error"}');
  } catch (error) {
    console.error("Document analysis error:", error);
    return { fields: [], notes: "Error analyzing document" };
  }
}

export async function decideNextAction(
  currentState: string,
  goal: string,
  history: string[],
  extraContext?: string
): Promise<AgentDecision> {
  const personalCtx = await getPersonalContext();
  const historyText =
    history.length > 0 ? `Recent actions:\n${history.slice(-10).join("\n")}` : "No previous actions.";

  const prompt = `
    ${personalCtx}

    You are a personal AI agent controlling an Outlook email browser session for the user
    described above. You understand their work, relationships, and priorities.

    Current state of the page:
    ${currentState}

    User's goal:
    ${goal}

    ${historyText}
    ${extraContext ? `\nAdditional context:\n${extraContext}` : ""}

    Available actions:
    - navigate_to_outlook: Go to Outlook inbox
    - get_email_list: Read the list of visible emails
    - open_email(index): Open a specific email by index
    - read_email: Read the currently open email fully
    - compose_email(to, subject, body): Compose a new email
    - reply_to_email(body): Reply to the currently open email
    - Sending is never autonomous. After composing a message, stop and report that operator approval is required.
    - scroll_down / scroll_up: Navigate the email list
    - navigate_to_folder(name): Go to a specific folder
    - search_emails(query): Search for emails
    - move_to_folder(name): Move selected email to folder
    - delete_email: Delete selected email
    - mark_as_read: Mark selected email as read
    - classify_email: AI-classify the current email
    - generate_draft: AI-draft a reply to the current email
    - analyze_context: Deep contextual analysis of current email
    - summarize_inbox: Summarize visible emails with priorities
    - search_papers(query): Search academic papers on Semantic Scholar
    - scout_web(name): Research someone's online presence
    - remember(summary, tags): Save something to memory for future reference
    - recall(query): Search past memories for context
    - navigate_to_url(url): Navigate to any URL
    - fill_form: Analyze and help fill a form/document on the current page
    - done: Goal achieved
    - wait: No action needed right now

    Think step by step. What single action best advances the goal?
    Return JSON: action, target (optional), params (optional object), reasoning.
  `;

  try {
    const response = await ai.models.generateContent({
      model: "gemini-2.0-flash",
      contents: prompt,
      config: {
        responseMimeType: "application/json",
        responseSchema: {
          type: Type.OBJECT,
          properties: {
            action: { type: Type.STRING },
            target: { type: Type.STRING },
            params: { type: Type.OBJECT, properties: {} },
            reasoning: { type: Type.STRING },
          },
          required: ["action", "reasoning"],
        },
      },
    });
    return JSON.parse(response.text || '{"action":"wait","reasoning":"Parse error"}');
  } catch (error) {
    console.error("Agent decision error:", error);
    return { action: "wait", reasoning: "Error in decision making" };
  }
}
