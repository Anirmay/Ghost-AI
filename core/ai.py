import google.generativeai as genai
from core.config import load_config, load_memory, append_to_memory

DEFAULT_PREFERRED_MODELS = [
    "models/gemini-flash-latest",
    "models/gemini-3.6-flash",
    "models/gemini-3.5-flash",
    "models/gemini-flash-lite-latest",
    "models/gemini-2.5-flash-lite",
    "models/gemini-2.0-flash",
    "models/gemini-2.5-flash",
    "models/gemini-pro-latest",
]

class GeminiClient:
    def __init__(self):
        self.history = []  # List of tuples: (role, text)

    def _fetch_available_models(self, api_key: str) -> list:
        """Query ModelService.ListModels to get available model ids (short names) that support generateContent.
        Caches results per api_key to avoid latency on every request.
        """
        if hasattr(self, "_cached_api_key") and self._cached_api_key == api_key and getattr(self, "_cached_available_models", None):
            return self._cached_available_models

        try:
            genai.configure(api_key=api_key)
            available = genai.list_models()
            out = []
            for m in available:
                name = getattr(m, "name", "")
                methods = getattr(m, "supported_generation_methods", [])
                if name and ("generateContent" in methods or not methods):
                    norm = self._normalize_model_name(name)
                    if not any(bad in norm for bad in ["embedding", "imagen", "aqa", "bison", "tts"]):
                        out.append(norm)
            if out:
                self._cached_api_key = api_key
                self._cached_available_models = out
                return out
        except Exception:
            pass
        return []

    def _normalize_model_name(self, name: str) -> str:
        normalized = name.strip()
        if not normalized:
            return ""
        return normalized if normalized.startswith("models/") else f"models/{normalized}"

    def _pick_candidate_models(self, preferred_models: list[str], available_models: list[str]) -> list[str]:
        candidates = []
        if available_models:
            normalized_available = [self._normalize_model_name(m) for m in available_models if m]
            for preferred in preferred_models:
                pref_norm = self._normalize_model_name(preferred)
                for av in normalized_available:
                    if av == pref_norm or preferred in av or av.endswith(preferred) or pref_norm.endswith(av):
                        if av not in candidates:
                            candidates.append(av)
            for av in normalized_available:
                if av not in candidates:
                    candidates.append(av)

        if not candidates:
            candidates = [self._normalize_model_name(m) for m in preferred_models]

        return candidates

    def _extract_response_text(self, response) -> str | None:
        """Safely extracts text output from a Gemini API response object and cleans thinking markers."""
        txt = None
        try:
            txt = response.text
        except Exception:
            pass
        if not txt and getattr(response, "candidates", None) and response.candidates:
            try:
                parts = response.candidates[0].content.parts
                txt = "".join(p.text for p in parts if hasattr(p, "text") and p.text)
            except Exception:
                pass

        if txt:
            # Strip any accidental chain-of-thought/reasoning headers or rule breakdowns
            thinking_markers = ("user input:", "context:", "goal:", "rule 1:", "rule 2:", "rule 3:", "rule 4:", "rule ", "standard ai:", "ghostai:", "persona:", "general definition:")
            lines = [l for l in txt.splitlines() if not l.strip().lower().startswith(thinking_markers)]
            cleaned = "\n".join(lines).strip()
            return cleaned if cleaned else txt.strip()

        return None

    def _is_aptitude_question(self, text: str) -> bool:
        txt = text.lower()
        keywords = ["km", "speed", "increased", "distance", "train", "work", "days", "complete", "rate", "together"]
        return any(k in txt for k in keywords)

    def _solve_aptitude_locally(self, text: str) -> str | None:
        """Try to solve a few common aptitude problem patterns locally.
        Returns a concise answer if solved, otherwise None.
        """
        try:
            s = text.replace('\n', ' ').replace(',', ' ')
            lower = s.lower()

            # Pattern: distance D, speed increased by v_inc, takes t_dec less hours
            if "km" in lower and "increas" in lower and "hour" in lower:
                import re, math
                # Extract numbers
                nums = [float(n) for n in re.findall(r"\d+(?:\.\d+)?", s)]
                # Heuristic extraction: distance first (e.g., 360), speed increase (10), time decrease (1)
                if len(nums) >= 3:
                    D = nums[0]
                    v_inc = nums[1]
                    t_dec = nums[2]
                    # Solve v^2 + v_inc*v - (D*v_inc/t_dec) = 0
                    R = D * v_inc / t_dec
                    disc = v_inc * v_inc + 4 * R
                    if disc < 0:
                        return None
                    v = (-v_inc + math.sqrt(disc)) / 2
                    # Prefer a 2-decimal answer for precision
                    v_precise = round(v, 2)
                    # Try to detect MCQ choices in the text and pick closest if within tolerance
                    mc_matches = re.findall(r"\b([A-D])\)\s*(\d+(?:\.\d+)?)", s)
                    if mc_matches:
                        # mc_matches is list of tuples (label, value)
                        closest = None
                        best_diff = None
                        for label, val in mc_matches:
                            try:
                                num = float(val)
                                diff = abs(num - v_precise)
                                if best_diff is None or diff < best_diff:
                                    best_diff = diff
                                    closest = (label, int(round(num)))
                            except Exception:
                                continue
                        if best_diff is not None and best_diff <= 1.0:
                            return f"Answer: {closest[0]}) {closest[1]} km/h"
                    return f"Answer: {v_precise} km/h"

            # Pattern: work rates A,B,C times given, A leaves after X days, B leaves Y days before completion
            if "work" in lower and "days" in lower and "together" in lower:
                import re
                nums = [float(n) for n in re.findall(r"\d+(?:\.\d+)?", s)]
                # Heuristic: first three numbers are days for A,B,C (their individual times)
                # Then there may be values for days worked like 5 and the '5 days before completion'
                if len(nums) >= 5:
                    tA, tB, tC = nums[0], nums[1], nums[2]
                    dayA_leaves = nums[3]
                    # The last value is the 'before completion' days (e.g., 5)
                    before_completion = nums[4]
                    rA = 1.0 / tA
                    rB = 1.0 / tB
                    rC = 1.0 / tC
                    # Total work: rA*dayA_leaves + rB*(T - before_completion) + rC*T = 1
                    # Solve for T: rB*(T - before_completion) + rC*T + rA*dayA_leaves = 1
                    # => T*(rB + rC) - rB*before_completion + rA*dayA_leaves = 1
                    denom = (rB + rC)
                    if denom == 0:
                        return None
                    T = (1 + rB * before_completion - rA * dayA_leaves) / denom
                    # Round to one decimal if needed
                    if abs(T - round(T)) < 1e-6:
                        T_out = int(round(T))
                    else:
                        T_out = round(T, 2)
                    return f"Answer: {T_out} days"
        except Exception:
            return None
        return None

    def _solve_code_output_locally(self, text: str) -> str | None:
        """Attempt to evaluate simple 'what is the output' style code snippets for C-like assignments and prints.
        Handles:
        - pointer write to a variable pattern
        - arithmetic swap via temporary-free arithmetic
        - simple sequence of int assignments and operations followed by printf of variables
        Returns a short string like '25' or '10 5' when possible.
        """
        try:
            import re

            s = text.replace('\n', ' ').replace(';', ' ; ')

            # Pointer assignment pattern: int x = NUM; int *p = &x; *p = NUM; printf("%d", x);
            m = re.search(r"int\s+([a-zA-Z_]\w*)\s*=\s*(\d+)\s*;\s*int\s*\*\s*([a-zA-Z_]\w*)\s*=\s*&\1\s*;\s*\*\3\s*=\s*(\d+)\s*;\s*printf\([^\)]*%d[^\)]*\)",
                          s)
            if m:
                val = int(m.group(4))
                return str(val)

            # Swap via arithmetic pattern: int a = A, b = B; a = a + b; b = a - b; a = a - b; printf("%d %d", a, b);
            m2 = re.search(r"int\s+([a-zA-Z_]\w*)\s*=\s*(\d+)\s*,\s*([a-zA-Z_]\w*)\s*=\s*(\d+)\s*;.*printf\([^\)]*%d\s*%d[^\)]*\)", s)
            if m2:
                a_name = m2.group(1)
                a_val = int(m2.group(2))
                b_name = m2.group(3)
                b_val = int(m2.group(4))
                # perform the arithmetic swap sequence if present
                if "a = a + b" in s or f"{a_name} = {a_name} + {b_name}" in s:
                    a = a_val + b_val
                    b = a - b_val
                    a = a - b
                    return f"{a} {b}"

            # General simple interpreter for assignments and printf
            # Extract initial int declarations like: int a = 5, b = 10;
            decls = re.findall(r"int\s+([^;]+);", s)
            vars = {}
            for decl in decls:
                parts = decl.split(',')
                for p in parts:
                    p = p.strip()
                    m3 = re.match(r"([a-zA-Z_]\w*)\s*=\s*(-?\d+)", p)
                    if m3:
                        vars[m3.group(1)] = int(m3.group(2))

            # Run simple assignments like 'a = a + b' or 'a = 25'
            assigns = re.findall(r"([a-zA-Z_]\w*)\s*=\s*([^;]+);", s)
            for name, expr in assigns:
                expr = expr.strip()
                # skip declarations already processed
                if name in vars and re.search(r"\bint\b", expr):
                    continue
                # Replace var names in expr with their numeric values
                expr_eval = expr
                for vname, vval in list(vars.items()):
                    expr_eval = re.sub(rf"\b{vname}\b", str(vval), expr_eval)
                # Remove whitespace
                expr_eval = expr_eval.replace(' ', '')
                # Allow only digits and +-*/() in the final expression
                if re.match(r"^[0-9+\-*/()]+$", expr_eval):
                    try:
                        val = int(eval(expr_eval))
                        vars[name] = val
                    except Exception:
                        pass

            # Find printf order
            pf = re.search(r"printf\([^\)]*\"?%d(?:\s*%d)*\"?[^\)]*\)", s)
            if pf:
                # extract variable names from the printf arguments (simple heuristic)
                args = re.findall(r"printf\([^\)]*,\s*(.*)\)", s)
                if args:
                    arglist = args[0]
                    # split by comma and extract variable tokens
                    toks = [t.strip() for t in arglist.split(',')[:4]]
                    out_vals = []
                    for t in toks:
                        # variable name only
                        mvar = re.match(r"([a-zA-Z_]\w*)", t)
                        if mvar:
                            name = mvar.group(1)
                            if name in vars:
                                out_vals.append(str(vars[name]))
                    if out_vals:
                        return ' '.join(out_vals)
        except Exception:
            return None
        return None

    def clear_history(self):
        """Clears the conversational chat history."""
        self.history = []

    def _get_sanitized_history_contents(self, current_question: str) -> list[dict]:
        """
        Builds a strictly valid, alternating user <-> model conversation history payload
        for the Gemini API, maintaining full multi-turn conversation memory.
        """
        contents = []
        expected_role = "user"

        for role, text in self.history:
            if not text or not text.strip():
                continue
            gemini_role = "user" if role == "user" else "model"
            if gemini_role == expected_role:
                contents.append({
                    "role": gemini_role,
                    "parts": [{"text": text.strip()}]
                })
                expected_role = "model" if gemini_role == "user" else "user"

        # If history ended on a user role without a model turn, pop it to maintain valid structure
        if contents and contents[-1]["role"] == "user":
            contents.pop()

        # Append the new user question
        contents.append({
            "role": "user",
            "parts": [{"text": current_question.strip()}]
        })
        return contents

    def ask(self, question: str) -> str:
        """
        Sends the question to Gemini API with full local memory and rolling chat history.
        Intercepts memory storage commands (e.g. 'remember that...').
        """
        # 1. Check for memory storage trigger commands
        clean_q = question.strip().lower()
        remember_triggers = ["remember that", "save to memory that", "store that", "write down that", "remember"]
        
        for trigger in remember_triggers:
            if clean_q.startswith(trigger):
                # Extract the fact to remember
                fact = question[len(trigger):].strip()
                # Remove leading colons or punctuation
                if fact.startswith(":") or fact.startswith(","):
                    fact = fact[1:].strip()
                # Remove quotes if the user said them
                if fact.startswith('"') and fact.endswith('"'):
                    fact = fact[1:-1].strip()
                if fact.startswith("'") and fact.endswith("'"):
                    fact = fact[1:-1].strip()
                    
                if fact:
                    append_to_memory(fact)
                    return f"💾 **Memory Stored Successfully!**\n\nI've recorded the following fact in your local knowledge base:\n\n> *\"{fact}\"*\n\nI will use this context in all future answers!"

        # 2. Load API key and memory contents
        config = load_config()
        api_key = config.get("api_key", "").strip()
        
        if not api_key:
            return (
                "⚠️ **Gemini API Key Missing!**\n\n"
                "Please click the **Settings** button (gear icon) on the tray or overlay "
                "and paste your free Gemini API Key from Google AI Studio."
            )

        memory_content = load_memory()
        
        # 3. Construct System Prompt with Multi-Turn Conversation Rules
        system_instruction = (
            "You are GhostAI, an ultra-fast, intelligent, and highly contextual assistant.\n"
            "CRITICAL MULTI-TURN CONVERSATION INSTRUCTIONS:\n"
            "- You maintain full conversation history with the user.\n"
            "- Pay careful attention to all previous user questions, requests, and your previous answers in the conversation thread.\n"
            "- If the user asks to correct, revise, explain, fix, or build upon a previous answer or question (e.g. 'correct the previous answer', 'rewrite that', 'fix question 1'), refer directly to the conversation history above and provide the updated/corrected final answer.\n"
            "- Provide ONLY the direct final answer. DO NOT output any internal thoughts, reasoning steps, or rule breakdowns.\n"
            "- Keep answers clear, accurate, and concise. Format code in markdown code blocks with the correct language.\n\n"
            "Below is the user's private local knowledge base:\n"
            "--------------------------------------------------\n"
            f"{memory_content}\n"
            "--------------------------------------------------\n"
        )

        # 4. Prepare sanitized alternating message history list for API
        contents = self._get_sanitized_history_contents(question)

        # 5. Execute Gemini request using the official client.
        available_models = self._fetch_available_models(api_key)
        candidate_models = self._pick_candidate_models(DEFAULT_PREFERRED_MODELS, available_models)

        genai.configure(api_key=api_key)
        last_err = ""
        for model_name in candidate_models:
            try:
                model = genai.GenerativeModel(model_name, system_instruction=system_instruction)
                response = model.generate_content(contents, generation_config={"temperature": 0.2})
                answer = self._extract_response_text(response)
            except Exception as e:
                last_err = f"Model {model_name} failed: {e}"
                continue

            if answer:
                self.history.append(("user", question))
                self.history.append(("model", answer))
                if len(self.history) > 30:
                    self.history = self.history[-30:]
                return answer

        if self._is_aptitude_question(question):
            local = self._solve_aptitude_locally(question)
            if local:
                return local

        code_local = self._solve_code_output_locally(question)
        if code_local:
            return code_local

        return f"❌ **Error querying Gemini API!**\n\nDetails: {last_err}\n\n*Please verify your API key or internet connection.*"

    def ask_autopilot(self, snippet: str) -> str:
        """
        Specialized Meeting Copilot evaluator.
        Analyzes meeting conversation snippets in real-time.
        Filters out general chatter, greetings, and administrative comments.
        If a question is detected, answers it concisely. Otherwise, returns '[IGNORE]'.
        """
        config = load_config()
        api_key = config.get("api_key", "").strip()
        if not api_key:
            return "[IGNORE]" # Fail silently if API key is missing in background auto-pilot

        memory_content = load_memory()
        
        system_instruction = (
            "You are GhostAI, an invisible real-time Meeting Copilot. "
            "You are listening to a live meeting/conversation. "
            "Your job is to analyze the incoming transcription snippet, determine if it represents a question or request for information that needs answering, and provide a highly concise, direct, and correct answer.\n\n"
            "CRITICAL INSTRUCTIONS:\n"
            "1. Determine if the snippet contains a question or query (direct or indirect) e.g., 'What is...', 'How do we...', 'Explain X', 'Why does...'.\n"
            "2. If it is NOT a question (e.g. general chatter, small talk, greetings, agreement, screen-sharing setup like 'I can see it', 'Let's wait'), you MUST reply with EXACTLY the single word: [IGNORE]. Do not say anything else.\n"
            "3. If it IS a question, write a beautifully formatted, extremely concise answer immediately. Never say conversational fluff ('Here is the answer', 'Based on your notes'). Go straight to the point.\n"
            "4. Format code elegantly in markdown blocks, and use brief bold headers or bullet points.\n\n"
            "Below is the user's private local knowledge base. Use it to answer correctly whenever relevant:\n"
            "--------------------------------------------------\n"
            f"{memory_content}\n"
            "--------------------------------------------------\n"
        )
        
        prompt = f"Analyze the following conversation snippet:\n\"{snippet}\""
        
        available_models = self._fetch_available_models(api_key)
        candidate_models = self._pick_candidate_models(DEFAULT_PREFERRED_MODELS, available_models)

        genai.configure(api_key=api_key)
        last_err = ""
        for model_name in candidate_models:
            try:
                model = genai.GenerativeModel(model_name, system_instruction=system_instruction)
                response = model.generate_content([{
                    "role": "user",
                    "parts": [{"text": prompt}]
                }], generation_config={"temperature": 0.1})
                answer = self._extract_response_text(response)
                if answer:
                    return answer.strip()
            except Exception as e:
                last_err = str(e)
                continue

        if self._is_aptitude_question(snippet):
            local = self._solve_aptitude_locally(snippet)
            if local:
                return local
        code_local = self._solve_code_output_locally(snippet)
        if code_local:
            return code_local

        return "[IGNORE]"

    def ask_interview(self, question: str) -> str:
        """
        Interview Mode AI — answers EVERY detected phrase immediately.
        Unlike ask_autopilot(), this never filters/ignores anything.
        Maintains a rolling interview conversation history for context.
        Used in hands-free Interview Mode where every question must be answered.
        """
        config = load_config()
        api_key = config.get("api_key", "").strip()
        if not api_key:
            return (
                "⚠️ **API Key Missing!**\n\n"
                "Go to Settings and paste your Gemini API key."
            )

        memory_content = load_memory()

        system_instruction = (
            "You are GhostAI, an invisible real-time Interview Copilot running on the user's screen.\n"
            "The user is in a LIVE JOB INTERVIEW. Audio is being transcribed in real time.\n"
            "Your job: read each incoming transcription and immediately provide the BEST POSSIBLE answer "
            "the user should say in response.\n\n"
            "RULES:\n"
            "1. ALWAYS respond — never skip, never say [IGNORE]. Every phrase might be a question.\n"
            "2. Be extremely concise and structured. The user needs to glance and speak.\n"
            "3. If the transcription is a question → give a sharp, direct answer in bullet points.\n"
            "4. If it is a statement/context → give a very brief 1-line acknowledgment or follow-up suggestion.\n"
            "5. Format code in markdown blocks. Use **bold** for key terms.\n"
            "6. Never say 'Sure', 'Great question', or conversational filler. Go straight to the answer.\n"
            "7. Keep answers under 100 words unless code/technical detail is required.\n\n"
            "The user's private knowledge base (use to personalize answers):\n"
            "--------------------------------------------------\n"
            f"{memory_content}\n"
            "--------------------------------------------------\n"
        )

        # Build conversation history for context
        contents = self._get_sanitized_history_contents(f"Transcription: \"{question}\"")

        available_models = self._fetch_available_models(api_key)
        candidate_models = self._pick_candidate_models(DEFAULT_PREFERRED_MODELS, available_models)

        genai.configure(api_key=api_key)
        last_err = ""
        for model_name in candidate_models:
            try:
                model = genai.GenerativeModel(model_name, system_instruction=system_instruction)
                response = model.generate_content(contents, generation_config={"temperature": 0.15})
                answer = self._extract_response_text(response)
                if answer:
                    self.history.append(("user", question))
                    self.history.append(("model", answer))
                    if len(self.history) > 30:
                        self.history = self.history[-30:]
                    return answer.strip()
            except Exception as e:
                last_err = str(e)
                continue

        if self._is_aptitude_question(question):
            local = self._solve_aptitude_locally(question)
            if local:
                return local
        code_local = self._solve_code_output_locally(question)
        if code_local:
            return code_local

        return f"❌ **API Error:** {last_err}"
