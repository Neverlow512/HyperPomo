# src/gemini_assistant.py
import google.generativeai as genai
import os

# System prompt for task management and related queries
TASK_MANAGEMENT_PROMPT_INSTRUCTION = """\
You are a helpful assistant for the HyperPomo application. Your goal is to help the user manage their tasks.
The user may have ADHD, so task breakdown and clear, actionable steps are helpful.
When responding to task-related requests, use the following structured formats:

1.  **Create Task:** If the user asks to create a new task, respond with:
    `CREATE_TASK: DESCRIPTION: [task description]; DUE_DATE: [YYYY-MM-DD or ""]; POMODOROS: [number or ""]`
    Example: `CREATE_TASK: DESCRIPTION: Write blog post about time management; DUE_DATE: 2024-07-15; POMODOROS: 3`
    If due date or pomodoros are not specified, use "" for the value.

2.  **Query Tasks for a Date:** If the user asks to list tasks for a specific date, respond with:
    `QUERY_TASKS_FOR_DATE: DATE: [YYYY-MM-DD]`
    Example: `QUERY_TASKS_FOR_DATE: DATE: 2024-07-12`

3.  **Schedule Task:** If the user asks to schedule an existing task (they might provide an ID or describe it), respond with:
    `SCHEDULE_TASK: TASK_ID: [task_id or task_description]; DUE_DATE: [YYYY-MM-DD]`
    Example: `SCHEDULE_TASK: TASK_ID: Finish report; DUE_DATE: 2024-07-13`
    If the user provides a description instead of an ID, use the description as TASK_ID.

4.  **Task Estimation Suggestion:** If the user asks for help estimating Pomodoros for a task, respond with:
    `TASK_ESTIMATE_SUGGESTION: DESCRIPTION: [task description]; SUGGESTED_POMOS: [number]; REASONING: [optional brief reason]`
    Example: `TASK_ESTIMATE_SUGGESTION: DESCRIPTION: Research new marketing strategies; SUGGESTED_POMOS: 4; REASONING: Requires focused research and outlining.`

For other general conversation, respond naturally. If the request is ambiguous, ask for clarification.
Do not add any conversational fluff before or after the structured response if a structured response is applicable.
"""

class GeminiAssistant:
    def __init__(self, api_key, model_name="gemini-pro"):
        self.api_key = api_key
        self.model_name = model_name
        self.model = None
        self._configure()

    def _configure(self):
        if not self.api_key:
            # print("Gemini API key is missing.") # Or raise an error, or handle silently
            return
        try:
            genai.configure(api_key=self.api_key)
            self.model = genai.GenerativeModel(self.model_name)
            # print(f"Gemini Assistant configured with model: {self.model_name}")
        except Exception as e:
            print(f"Error configuring Gemini: {e}")
            self.model = None

    def send_message(self, message_text):
        if not self.model:
            return "Error: Gemini model is not configured. Please check API key and settings."

        # Prepend the task management system prompt to the user's message
        # For more sophisticated chat, this would be part of a history or a specific instruction set.
        full_prompt = TASK_MANAGEMENT_PROMPT_INSTRUCTION + "\n\nUser query: " + message_text

        try:
            # For now, simple non-streaming generation. Streaming for chat later.
            response = self.model.generate_content(full_prompt)
            return response.text
        except Exception as e:
            print(f"Error sending message to Gemini: {full_prompt} | Error: {e}")
            # Check for specific API errors if possible, e.g., authentication, quota
            if "API_KEY_INVALID" in str(e) or "API_KEY_MISSING" in str(e) :
                 return "Error: Gemini API key is invalid or missing. Please check your settings."
            if "quota" in str(e).lower():
                return "Error: Gemini API quota exceeded. Please check your account."
            return f"Error communicating with Gemini: {str(e)[:100]}" # Truncate long errors

if __name__ == '__main__':
    # Example Usage (requires API key to be set as an environment variable for this test)
    # or directly passed if testing.
    # IMPORTANT: Do not commit actual API keys to version control.
    # test_api_key = os.environ.get("GEMINI_API_KEY")
    # if test_api_key:
    #     assistant = GeminiAssistant(api_key=test_api_key, model_name="gemini-pro")
    #     if assistant.model:
    #         prompt = "What is the capital of France?"
    #         print(f"Sending prompt: {prompt}")
    #         reply = assistant.send_message(prompt)
    #         print(f"Gemini Reply: {reply}")
    #     else:
    #         print("Failed to initialize Gemini model for testing.")
    # else:
    #     print("GEMINI_API_KEY environment variable not set. Skipping direct test.")
    pass # Keep __main__ block minimal or for controlled tests
