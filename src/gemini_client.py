import google.generativeai as genai
import os

class GeminiClient:
    def __init__(self, api_key, model_name="models/gemini-1.5-flash-latest"):
        self.api_key = api_key
        self.model_name = model_name
        self._configure_client()
        self.model = None
        if self.api_key:
            try:
                self.model = genai.GenerativeModel(self.model_name)
            except Exception as e:
                print(f"Error initializing Gemini model: {e}")
                # Potentially raise an error or handle it by setting model to None

    def _configure_client(self):
        if self.api_key:
            try:
                genai.configure(api_key=self.api_key)
            except Exception as e:
                print(f"Error configuring Gemini API key: {e}")
                # This might indicate an invalid API key format or other issues.
        else:
            print("Gemini API key is not set. Client will not be functional.")

    def is_configured(self):
        return self.api_key and self.model is not None

    async def send_message(self, message_text):
        if not self.is_configured():
            return "Error: Gemini client is not configured (API key or model missing/invalid)."

        try:
            # For simplicity, using generate_content for now.
            # For actual chat, would need to manage history.
            response = await self.model.generate_content_async(message_text)
            return response.text
        except Exception as e:
            print(f"Error sending message to Gemini: {e}")
            return f"Error communicating with Gemini: {str(e)}"

    def update_config(self, api_key, model_name):
        self.api_key = api_key
        self.model_name = model_name
        self._configure_client() # Re-configure with new key
        if self.api_key:
            try:
                self.model = genai.GenerativeModel(self.model_name) # Re-initialize model
            except Exception as e:
                print(f"Error re-initializing Gemini model with new config: {e}")
                self.model = None
        else:
            self.model = None

# Example Usage (for testing purposes, will be removed or commented out)
# async def main():
#     # Replace with a valid API key for testing
#     test_api_key = os.environ.get("GEMINI_API_KEY")
#     if not test_api_key:
#         print("Please set the GEMINI_API_KEY environment variable for testing.")
#         return

#     client = GeminiClient(api_key=test_api_key, model_name="models/gemini-1.5-flash-latest")
#     if client.is_configured():
#         print("Gemini client configured. Sending test message...")
#         response_text = await client.send_message("Hello Gemini, how are you today?")
#         print(f"Gemini's response: {response_text}")
#     else:
#         print("Gemini client failed to configure.")

# if __name__ == "__main__":
#     import asyncio
#     asyncio.run(main())
