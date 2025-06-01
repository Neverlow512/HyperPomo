# src/gemini_assistant.py
import google.generativeai as genai
import os

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

        try:
            # For now, simple non-streaming generation. Streaming for chat later.
            response = self.model.generate_content(message_text)
            return response.text
        except Exception as e:
            print(f"Error sending message to Gemini: {e}")
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
