"""
SupportBrain - Customer Support Agent with Groq LLM
===================================================
This module isolates all LLM interaction logic using the Groq API.

Responsibilities:
1. Formulates the prompt incorporating:
   - Current customer details (name, company, product)
   - Chat history
   - Recalled memories retrieved from Hindsight (previous problems, solutions, preferences)
2. Calls the Groq LLM (e.g., llama-3.3-70b-versatile).
3. If relevant memories exist, instructs the model to reference past solutions directly!
4. Extracts new knowledge (customer facts, reported issues, applied fixes) to store in Hindsight.
5. Gracefully handles missing API keys, rate limits, and network errors.
"""

import os
import re
import json
import logging
from typing import Any, Dict, List, Optional, Tuple
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

logger = logging.getLogger("supportbrain-agent")

# Try importing the official Groq client
try:
    from groq import Groq
    GROQ_AVAILABLE = True
except ImportError:
    GROQ_AVAILABLE = False
    logger.warning("Groq SDK not installed. Falling back to simulation mode.")


class SupportAgent:
    """
    AI Customer Support Agent powered by Groq and guided by Hindsight Memory.
    """

    def __init__(self):
        self.api_key = os.getenv("GROQ_API_KEY", "").strip()
        self.model = os.getenv("GROQ_MODEL", "llama-3.3-70b-versatile")
        self.client = None

        if GROQ_AVAILABLE and self.api_key and not self.api_key.startswith("your_"):
            try:
                self.client = Groq(api_key=self.api_key)
                logger.info(f"Groq client initialized with model '{self.model}'.")
            except Exception as e:
                logger.error(f"Failed to initialize Groq client: {e}")
                self.client = None
        else:
            logger.info("Groq API key not set or invalid. Running in intelligent simulation mode.")

    def is_configured(self) -> bool:
        """Returns True if Groq API key is set and client is ready."""
        return self.client is not None

    def build_system_prompt(
        self,
        customer_name: Optional[str],
        company: Optional[str],
        product: Optional[str],
        recalled_memories: List[Dict[str, Any]]
    ) -> str:
        """
        Builds the system prompt that equips the LLM with customer context
        and previous Hindsight memories.
        """
        cust_str = customer_name or "Unknown Customer"
        comp_str = company or "Unspecified Company"
        prod_str = product or "General Support"

        # Format memories for the LLM
        memories_text = ""
        if recalled_memories:
            memories_text = "### RELEVANT PREVIOUS EXPERIENCES FROM HINDSIGHT MEMORY:\n"
            for idx, mem in enumerate(recalled_memories, 1):
                memories_text += f"{idx}. Customer: {mem.get('customer_name') or cust_str}\n"
                if mem.get('company'):
                    memories_text += f"   Company: {mem.get('company')}\n"
                if mem.get('product'):
                    memories_text += f"   Product: {mem.get('product')}\n"
                if mem.get('issue'):
                    memories_text += f"   Previous Issue: {mem.get('issue')}\n"
                if mem.get('solution'):
                    memories_text += f"   Previous Solution: {mem.get('solution')}\n"
                if mem.get('result'):
                    memories_text += f"   Result: {mem.get('result')}\n"
                if mem.get('text'):
                    memories_text += f"   Details: {mem.get('text')}\n"
                memories_text += "\n"
        else:
            memories_text = "No previous support history found in Hindsight for this query.\n"

        prompt = f"""You are SupportBrain, an expert, friendly, and proactive AI customer support agent.
You possess a persistent memory bank powered by Hindsight.

CURRENT CUSTOMER PROFILE:
- Customer Name: {cust_str}
- Company: {comp_str}
- Product: {prod_str}

{memories_text}
CRITICAL MEMORY INSTRUCTIONS:
1. If the customer mentions recurring or past issues (like 'the login problem again', 'the same issue', etc.), check the Hindsight memories above!
2. If a matching previous issue and solution are present, EXPLICITLY reference that you remember what happened previously and suggest the verified solution!
   Example: "I remember you had a similar session issue previously, and clearing the browser session resolved it. Would you like to try that again?"
3. If the customer shares new details about themselves, their company, their product, or a new issue/fix, acknowledge it warmly so they know it is saved.
4. Keep your answer natural, concise, helpful, and empathetic. Do not invent fake previous interactions not present in the memory or conversation.
"""
        return prompt

    async def generate_response(
        self,
        customer_name: Optional[str],
        company: Optional[str],
        product: Optional[str],
        user_message: str,
        chat_history: Optional[List[Dict[str, str]]] = None,
        recalled_memories: Optional[List[Dict[str, Any]]] = None
    ) -> Tuple[str, Optional[Dict[str, Any]]]:
        """
        Generates the AI customer support response.
        Returns:
            - response_text: The agent's reply
            - extracted_info: Newly discovered facts to retain in Hindsight (or None)
        """
        memories = recalled_memories or []
        system_prompt = self.build_system_prompt(customer_name, company, product, memories)

        # 1. If Groq is configured, execute via Groq LLM
        if self.is_configured():
            try:
                messages = [{"role": "system", "content": system_prompt}]

                # Include past chat turns (up to last 6 for recency)
                if chat_history:
                    for turn in chat_history[-6:]:
                        role = "user" if turn.get("role") == "user" else "assistant"
                        messages.append({"role": role, "content": turn.get("content", "")})

                messages.append({"role": "user", "content": user_message})

                response = self.client.chat.completions.create(
                    model=self.model,
                    messages=messages,
                    temperature=0.3,
                    max_tokens=600
                )

                reply_text = response.choices[0].message.content.strip()

                # Extract new facts for Hindsight
                extracted_info = self._extract_knowledge(user_message, reply_text, customer_name, company, product)
                return reply_text, extracted_info

            except Exception as e:
                logger.error(f"Error calling Groq API: {e}. Falling back to smart response.")

        # 2. Smart Simulation / Fallback Mode (Runs when GROQ_API_KEY is not set)
        return self._generate_fallback_response(
            customer_name=customer_name,
            company=company,
            product=product,
            user_message=user_message,
            memories=memories
        )

    def _generate_fallback_response(
        self,
        customer_name: Optional[str],
        company: Optional[str],
        product: Optional[str],
        user_message: str,
        memories: List[Dict[str, Any]]
    ) -> Tuple[str, Optional[Dict[str, Any]]]:
        """
        Intelligent rule-based fallback that demonstrates the exact Hindsight memory workflow
        even before a user adds a Groq API key.
        """
        msg_lower = user_message.lower()
        cust_display = customer_name or "there"

        # Check if the user is asking about a recurring problem
        login_related = any(w in msg_lower for w in ["login", "session", "sign in", "auth", "log in"])
        again_related = any(w in msg_lower for w in ["again", "same problem", "same issue", "recurring", "happening again"])

        # Look for relevant memory
        relevant_mem = None
        for m in memories:
            m_text = (m.get("issue", "") + " " + m.get("text", "")).lower()
            if login_related and ("session" in m_text or "login" in m_text):
                relevant_mem = m
                break
            elif "export" in msg_lower and "export" in m_text:
                relevant_mem = m
                break

        if not relevant_mem and memories:
            # If user asks "what do you remember" or general recall
            if any(w in msg_lower for w in ["remember", "who am i", "my company", "history", "previous"]):
                relevant_mem = memories[0]

        # Scenario A: User mentions login issue again & memory has previous resolution
        if (login_related or again_related) and relevant_mem:
            sol = relevant_mem.get("solution") or "clearing the browser session and cookies"
            reply = (
                f"Hello {cust_display}! I checked your history in Hindsight and remember you had a similar "
                f"session issue previously on {relevant_mem.get('product') or 'the dashboard'}. "
                f"Last time, **{sol}** resolved it completely. Would you like to try that again?"
            )
            extracted = {
                "issue": "Recurring session/login issue",
                "solution": "Advised repeating previous fix (clear browser session)",
                "result": "Pending customer verification"
            }
            return reply, extracted

        # Scenario B: User asks what the agent remembers
        if any(w in msg_lower for w in ["what do you remember", "my company", "who am i", "what product"]):
            if memories:
                first = memories[0]
                reply = (
                    f"Based on my Hindsight memory bank, you are **{first.get('customer_name') or cust_display}** "
                    f"from **{first.get('company') or company or 'your organization'}**, using **{first.get('product') or product or 'our platform'}**. "
                    f"I also have records of your previous support tickets and preferences saved!"
                )
            else:
                reply = (
                    f"I have you registered as **{cust_display}** from **{company or 'your team'}** using **{product or 'our service'}**. "
                    f"Any new issues or preferences you share will be saved directly into Hindsight."
                )
            return reply, None

        # Scenario C: User introduces themselves
        if any(w in msg_lower for w in ["my name is", "i work at", "we use"]):
            extracted = self._extract_knowledge(user_message, "", customer_name, company, product)
            new_name = extracted.get("customer_name") or cust_display
            new_comp = extracted.get("company") or company or "your company"
            new_prod = extracted.get("product") or product or "our platform"

            reply = (
                f"Nice to meet you, {new_name}! I have stored your details in Hindsight: "
                f"working at **{new_comp}** and using **{new_prod}**. "
                f"How can I assist you with your system today?"
            )
            return reply, extracted

        # Scenario D: User reports something worked or resolved
        if any(w in msg_lower for w in ["worked", "fixed", "resolved", "solved", "thank you", "thanks"]):
            reply = (
                f"Wonderful news! I have updated Hindsight with this resolution so that if anyone on your "
                f"team at {company or 'your company'} encounters this again, we can solve it immediately."
            )
            extracted = {
                "issue": "Recent support inquiry",
                "solution": "Verified resolution with customer",
                "result": "Successfully resolved"
            }
            return reply, extracted

        # Default helpful response
        reply = (
            f"Hello {cust_display}, thank you for reaching out! I'm SupportBrain. "
            f"I have connected to your Hindsight memory bank and I'm ready to assist with {product or 'your application'}. "
            f"Could you please share the details or error message you are experiencing?"
        )
        return reply, None

    def _extract_knowledge(
        self,
        user_message: str,
        agent_reply: str,
        current_name: Optional[str],
        current_comp: Optional[str],
        current_prod: Optional[str]
    ) -> Dict[str, Any]:
        """
        Heuristic extraction of customer profile and support resolutions
        from natural language messages.
        """
        extracted = {}

        # 1. Extract Customer Name
        name_match = re.search(r"(?:my name is|i am|i'm)\s+([A-Z][a-z]+(?:\s+[A-Z][a-z]+)?)", user_message, re.IGNORECASE)
        if name_match:
            extracted["customer_name"] = name_match.group(1).strip()

        # 2. Extract Company
        comp_match = re.search(r"(?:work at|work for|at|from)\s+([A-Z0-9][A-Za-z0-9\s&]+?)(?:\s+and|\s+we|\.|\,|$)", user_message, re.IGNORECASE)
        if comp_match:
            candidate = comp_match.group(1).strip()
            if len(candidate) > 2 and candidate.lower() not in ["home", "work", "here", "today"]:
                extracted["company"] = candidate

        # 3. Extract Product
        prod_match = re.search(r"(?:we use|i use|using|on)\s+([A-Z0-9][A-Za-z0-9\s]+?)(?:\.|\,|$)", user_message, re.IGNORECASE)
        if prod_match:
            candidate = prod_match.group(1).strip()
            if len(candidate) > 2 and candidate.lower() not in ["it", "this", "that", "chrome", "windows", "mac"]:
                extracted["product"] = candidate

        # 4. Extract Solution / Fix
        fix_match = re.search(r"(?:fixed it by|solved it by|solution was|clearing|restarted|resolved by)\s+([^.]+)", user_message, re.IGNORECASE)
        if fix_match:
            extracted["solution"] = fix_match.group(0).strip()
            extracted["result"] = "Successfully resolved"

        return extracted


# Global agent instance
support_agent = SupportAgent()
