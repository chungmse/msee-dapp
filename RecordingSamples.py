import pyaudio
import wave
import os
from datetime import datetime
from pydub import AudioSegment
import random

# Parameters
CHANNELS = 1
RATE = 22050
CHUNK = 1024
RECORD_SECONDS = 15
SEGMENT_DURATION = 5000  # Duration of each segment in milliseconds
NUM_SEGMENTS = 5
WAVE_OUTPUT_DIR = "recordings\\control"

# List of formats for PyAudio
FORMATS = [pyaudio.paInt16, pyaudio.paInt24, pyaudio.paInt32]

# Create output directory if it doesn't exist
if not os.path.exists(WAVE_OUTPUT_DIR):
    os.makedirs(WAVE_OUTPUT_DIR)


def get_filename(prefix="recording"):
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    return f"{prefix}_{timestamp}.wav"


# Initialize PyAudio
audio = pyaudio.PyAudio()

# Randomly select format for PyAudio
FORMAT = random.choice(FORMATS)

# Start recording
print("Recording...")
stream = audio.open(format=FORMAT, channels=CHANNELS, rate=RATE, input=True, frames_per_buffer=CHUNK)

frames = []

for _ in range(0, int(RATE / CHUNK * RECORD_SECONDS)):
    data = stream.read(CHUNK)
    frames.append(data)

print("Finished recording.")

# Stop recording
stream.stop_stream()
stream.close()
audio.terminate()

# Save the recording
recording_filename = get_filename()
file_path = os.path.join(WAVE_OUTPUT_DIR, recording_filename)
with wave.open(file_path, 'wb') as wf:
    wf.setnchannels(CHANNELS)
    wf.setsampwidth(audio.get_sample_size(FORMAT))
    wf.setframerate(RATE)
    wf.writeframes(b''.join(frames))

print(f"Recording saved to {file_path}")

# Load the recording with pydub
audio_segment = AudioSegment.from_wav(file_path)
total_duration = len(audio_segment)  # Duration in milliseconds

# Extract recording information for segment naming
recording_info = f"{os.path.splitext(recording_filename)[0]}"

# Generate random start times for segments
segment_start_times = sorted(random.sample(range(0, total_duration - SEGMENT_DURATION), NUM_SEGMENTS))

for i, start_time in enumerate(segment_start_times):
    start_time_ms = start_time
    end_time_ms = start_time_ms + SEGMENT_DURATION
    segment = audio_segment[start_time_ms:end_time_ms]
    segment_filename = os.path.join(
        WAVE_OUTPUT_DIR,
        f"{recording_info}_segment_{i + 1}_{start_time_ms // 1000}s.wav"
    )
    segment.export(segment_filename, format="wav")
    print(f"Segment saved to {segment_filename}")

print("All segments have been saved.")
