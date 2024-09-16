import requests
import time
import json


class SongDataService:
    def __init__(self):
        self.api_url = 'https://msee-api.mse19hn.com/recognize'

    def send_audio(self, audio_file_path):
        try:
            with open(audio_file_path, 'rb') as audio_file:
                files = {'file': ('recorded_audio.wav', audio_file, 'audio/wav')}
                response = requests.post(f"{self.api_url}/upload", files=files)

                # Check if the response is successful
                if response.status_code == 200:
                    return response.json()
                else:
                    return {"error": "Failed to upload audio"}
        except Exception as e:
            return {"error": f"Error in uploading audio"}

    def get_result(self, job_id, token):
        try:
            headers = {'Content-Type': 'application/json'}
            payload = json.dumps({"job_id": job_id, "token": token})
            response = requests.post(f"{self.api_url}/result", headers=headers, data=payload)

            if response.status_code == 200:
                return response.json()
            else:
                return {"error": "Failed to fetch song result"}
        except Exception as e:
            return {"error": f"Error in fetching song result"}
