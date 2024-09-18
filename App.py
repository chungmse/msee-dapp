import sys
import time
import wave
from datetime import datetime
from functools import partial

import requests
import sounddevice as sd
from PyQt5.QtCore import Qt, QThread, pyqtSignal, QBuffer, QIODevice, QUrl
from PyQt5.QtGui import QFont, QPalette, QColor, QPixmap
from PyQt5.QtMultimedia import QMediaContent, QMediaPlayer
from PyQt5.QtWidgets import QApplication, QWidget, QVBoxLayout, QPushButton, QLabel, QGraphicsDropShadowEffect, \
    QScrollArea, QHBoxLayout

from models.SongMetadata import SongMetadata
from services.SongDataService import SongDataService  # Import the service class


class AudioRecorderThread(QThread):
    recording_done = pyqtSignal(str)  # Signal to indicate recording is done
    error_occurred = pyqtSignal(str)  # Signal to indicate an error occurred

    def __init__(self):
        super().__init__()
        self.recorded_audio = None

    def run(self):
        duration = 5  # Record for 5 seconds
        sample_rate = 22050

        try:
            # Record audio
            audio_data = sd.rec(int(duration * sample_rate), samplerate=sample_rate, channels=1)
            sd.wait()  # Wait for the recording to finish

            # Save the recorded audio to a WAV file
            self.recorded_audio = "recorded_audio.wav"

            with wave.open(self.recorded_audio, 'wb') as wav_file:
                wav_file.setnchannels(2)
                wav_file.setsampwidth(2)
                wav_file.setframerate(sample_rate)
                wav_file.writeframes(audio_data.tobytes())

            # Emit signal to indicate recording is done
            self.recording_done.emit(self.recorded_audio)

        except Exception as e:
            # Emit signal to indicate an error occurred
            self.error_occurred.emit(f"Failed to record audio: {str(e)}")


class ProcessingThread(QThread):
    processing_done = pyqtSignal(dict)  # Signal to indicate processing is done with response data
    error_occurred = pyqtSignal(str)  # Signal to indicate an error occurred

    def __init__(self, audio_file_path):
        super().__init__()
        self.audio_file_path = audio_file_path
        self.service = SongDataService()  # Create an instance of the service class

    def run(self):
        if self.audio_file_path:
            try:
                # Send the recorded audio to the service
                response_data = self.service.send_audio(self.audio_file_path)

                if "error" in response_data:
                    self.error_occurred.emit(response_data["error"])
                else:
                    # Start polling for results
                    job_id = response_data.get("job_id")
                    token = response_data.get("token")
                self.poll_results(job_id, token)

            except Exception as e:
                self.error_occurred.emit(f"Failed to process audio: {str(e)}")
        else:
            self.error_occurred.emit("No audio recorded")

    def poll_results(self, job_id, token):
        while True:
            result_data = self.service.get_result(job_id, token)

            if "error" in result_data:
                self.error_occurred.emit(result_data["error"])
                return

            if "list_result" in result_data and result_data["list_result"]:
                # Emit signal with the result data
                self.processing_done.emit(result_data)
                return

            # Wait before polling again
            time.sleep(0.5)


def convert_unix_timestamp_to_date(timestamp):
    try:
        return datetime.fromtimestamp(timestamp).strftime('%d/%m/%Y')
    except Exception as e:
        return 'Unknown'


class ShazamCloneApp(QWidget):
    def __init__(self):
        super().__init__()

        # Set up the window
        self.setWindowTitle('Shazam Clone')
        self.setGeometry(100, 100, 400, 600)

        self.showMaximized()

        # Set up the background color (deep black for OLED)
        palette = QPalette()
        palette.setColor(QPalette.Window, QColor("#ffffff"))
        self.setPalette(palette)

        # Create a scrollable area for the entire app
        scroll_area = QScrollArea()
        scroll_area.setWidgetResizable(True)
        scroll_area.setStyleSheet("background-color: #ffffff; border: none;")

        # Main container widget
        main_widget = QWidget()
        main_layout = QVBoxLayout(main_widget)
        main_widget.setStyleSheet("background-color: #ffffff;")

        # Create the main button
        self.record_button = QPushButton("Start Listening", self)
        self.record_button.setStyleSheet("""
            QPushButton {
                background-color: #2675b4;
                border-radius: 100px;
                font-family: Arial;
                font-size: 24px;
                height: 200px;
                width: 200px;
                color: #E2E2E2;
            }
            QPushButton:hover {
                background-color: #3A3A3C;
            }
        """)
        shadow_effect = QGraphicsDropShadowEffect()
        shadow_effect.setBlurRadius(30)
        shadow_effect.setOffset(0, 10)
        shadow_effect.setColor(QColor(0, 0, 0, 150))
        self.record_button.setGraphicsEffect(shadow_effect)

        self.record_button.clicked.connect(self.start_listening)
        main_layout.addWidget(self.record_button, alignment=Qt.AlignCenter)

        # Song info UI setup
        song_info_widget = QWidget(self)
        song_info_layout = QVBoxLayout(song_info_widget)
        song_info_layout.setSpacing(10)
        song_info_widget.setStyleSheet("background-color: #ffffff;")
        song_info_layout.setContentsMargins(0, 20, 0, 0)

        self.song_image_label = QLabel(self)
        self.default_album_image = "assets/default_album.jpg"
        self.song_image_label.setPixmap(QPixmap(self.default_album_image).scaled(150, 150, Qt.KeepAspectRatio))
        self.song_image_label.setAlignment(Qt.AlignCenter)
        self.song_image_label.hide()
        song_info_layout.addWidget(self.song_image_label, alignment=Qt.AlignCenter)

        self.song_title_label = QLabel("", self)
        self.song_title_label.setFont(QFont("Arial", 24, QFont.Bold))
        self.song_title_label.setStyleSheet("color: #2675b4;")
        self.song_title_label.setAlignment(Qt.AlignCenter)
        song_info_layout.addWidget(self.song_title_label, alignment=Qt.AlignCenter)

        self.album_artist_label = QLabel("", self)
        self.album_artist_label.setFont(QFont("Arial", 18))
        self.album_artist_label.setStyleSheet("color: #2675b4;")
        self.album_artist_label.setAlignment(Qt.AlignCenter)
        song_info_layout.addWidget(self.album_artist_label, alignment=Qt.AlignCenter)

        self.genre_label = QLabel("", self)
        self.genre_label.setFont(QFont("Arial", 14))
        self.genre_label.setStyleSheet("color: #2675b4;")
        self.genre_label.setAlignment(Qt.AlignCenter)
        song_info_layout.addWidget(self.genre_label, alignment=Qt.AlignCenter)

        self.release_year_label = QLabel("", self)
        self.release_year_label.setFont(QFont("Arial", 14))
        self.release_year_label.setStyleSheet("color: #2675b4;")
        self.release_year_label.setAlignment(Qt.AlignCenter)
        song_info_layout.addWidget(self.release_year_label, alignment=Qt.AlignCenter)

        self.duration_label = QLabel("", self)
        self.duration_label.setFont(QFont("Arial", 14))
        self.duration_label.setStyleSheet("color: #2675b4;")
        self.duration_label.setAlignment(Qt.AlignCenter)
        song_info_layout.addWidget(self.duration_label, alignment=Qt.AlignCenter)

        # Initialize QMediaPlayer
        self.media_player = QMediaPlayer()

        # Initialize variables to handle audio state
        self.is_paused = True
        self.current_mp3_url = None

        main_layout.addWidget(song_info_widget, alignment=Qt.AlignCenter)

        # Add clickable label to reveal extra songs (hidden initially)
        self.reveal_link = QLabel('<a href="#">Not the songs you are looking for?</a>', self)
        self.reveal_link.setOpenExternalLinks(False)
        self.reveal_link.setStyleSheet("color: #2675b4;")  # Dimmed gray for link text
        self.reveal_link.linkActivated.connect(self.toggle_extra_songs)  # Connect click action
        self.reveal_link.hide()  # Hide the link at startup
        main_layout.addWidget(self.reveal_link, alignment=Qt.AlignCenter)

        # Extra songs container (hidden initially)
        self.extra_songs_widget = QWidget(self)
        self.extra_songs_layout = QVBoxLayout(self.extra_songs_widget)
        self.extra_songs_widget.setStyleSheet("background-color: #ffffff;")
        self.extra_songs_widget.hide()  # Hide initially
        self.current_playing_button = None

        # Add the extra songs widget to the main layout
        main_layout.addWidget(self.extra_songs_widget, alignment=Qt.AlignCenter)

        # Set the main widget inside the scroll area
        scroll_area.setWidget(main_widget)
        main_layout_container = QVBoxLayout(self)
        main_layout_container.addWidget(scroll_area)
        self.setLayout(main_layout_container)

        # Audio-related variables
        self.recorded_audio = None

        # Create threads
        self.audio_recorder_thread = AudioRecorderThread()
        self.processing_thread = None

        # Connect signals
        self.audio_recorder_thread.recording_done.connect(self.update_ui_for_processing)
        self.audio_recorder_thread.error_occurred.connect(self.show_error)

    def start_listening(self):
        # Clear previous song info
        self.clear_song_info()

        # Update UI to show listening state
        self.record_button.setText("Listening...")
        self.record_button.setEnabled(False)  # Disable button during recording

        # Start the recording thread
        self.audio_recorder_thread.start()

    def update_ui_for_processing(self, audio_file_path):
        # Update UI to show processing state
        self.record_button.setText("Processing...")
        self.record_button.setEnabled(False)  # Disable button during processing

        # Start the processing thread
        self.processing_thread = ProcessingThread(audio_file_path)
        self.processing_thread.processing_done.connect(self.handle_response)
        self.processing_thread.error_occurred.connect(self.show_error)
        self.processing_thread.start()

    def handle_response(self, response_data):
        if "list_result" in response_data and response_data["list_result"]:
            # Map the first result to SongMetadata
            first_result = response_data["list_result"][0]
            song_metadata = SongMetadata(
                title=first_result.get('title', 'Unknown'),
                artistsNames=first_result.get('artistsNames', 'Unknown'),
                category=first_result.get('category', 'Unknown'),
                duration=first_result.get('duration', 0),
                link=first_result.get('link', ''),
                releaseDate=first_result.get('releaseDate', 0),
                thumbnailM=first_result.get('thumbnailM', self.default_album_image),
                mp3url=first_result.get('mp3url', '')
            )

            # Update UI with the song metadata
            self.song_title_label.setText(song_metadata.title)
            self.album_artist_label.setText(f"{song_metadata.artistsNames}")
            self.release_year_label.setText(f"Release Date: {song_metadata.formatted_release_date()}")
            self.duration_label.setText(f"Duration: {song_metadata.formatted_duration()}")

            # Download and set the album image
            self.set_album_image(song_metadata.thumbnailM)

            # Set the play button only if mp3_url is available
            self.current_mp3_url = song_metadata.mp3url
            self.play_audio(song_metadata.mp3url)

            # Check if extra songs are available
            if len(response_data.get("list_result", [])) > 1:
                # Show the reveal link
                self.reveal_link.setVisible(True)

                # Populate the extra songs section
                list_result = response_data["list_result"]

                # Ensure we only display up to 4 extra songs
                for i in range(0, 5):
                    song = SongMetadata(
                        title=list_result[i].get('title', 'Unknown'),
                        artistsNames=list_result[i].get('artistsNames', 'Unknown'),
                        category=list_result[i].get('category', 'Unknown'),
                        duration=list_result[i].get('duration', 0),
                        link=list_result[i].get('link', ''),
                        releaseDate=list_result[i].get('releaseDate', 0),
                        thumbnailM=list_result[i].get('thumbnailM', self.default_album_image),
                        mp3url=list_result[i].get('mp3url', '')
                    )

                    # Create a container widget with horizontal layout
                    container_widget = QWidget(self)
                    h_layout = QHBoxLayout(container_widget)

                    # Update label text
                    label_text = f"{song.title} - {song.artistsNames}"
                    song_label = QLabel(label_text, self)
                    song_label.setFont(QFont("Arial", 16))
                    song_label.setStyleSheet("color: #2675b4;")  # White text
                    h_layout.addWidget(song_label)

                    # Add duration label beside each song
                    duration_label = QLabel(song.formatted_duration(), self)
                    duration_label.setFont(QFont("Arial", 14))
                    duration_label.setStyleSheet("color: #2675b4;")  # Muted gray for duration
                    h_layout.addWidget(duration_label)

                    # Add play button beside each song
                    play_button = QPushButton("▶", self)
                    play_button.setObjectName(f"button{i}")
                    play_button.setFixedSize(40, 40)
                    play_button.setStyleSheet("""\
                                        QPushButton {
                                            background-color: #2675b4;
                                            border-radius: 10px;
                                            font-family: Arial;
                                            font-size: 16px;
                                            height: 40px;
                                            width: 40px;
                                            color: #ffffff;
                                        }
                                        QPushButton:hover {
                                            background-color: #3A3A3C;
                                        }
                                    """)
                    play_button.clicked.connect(partial(self.play_audio, song.mp3url, play_button))
                    h_layout.addWidget(play_button)

                    # Add the container widget to the extra songs layout
                    self.extra_songs_layout.addWidget(container_widget)

                    # Show the extra songs widget
                self.extra_songs_widget.setVisible(False)
            else:
                # Hide the extra songs section and the reveal link if no extra songs are available
                self.extra_songs_widget.setVisible(False)
                self.reveal_link.setVisible(False)

        else:
            self.song_title_label.setText("No song found")
            self.album_artist_label.clear()
            self.release_year_label.clear()
            self.duration_label.clear()

        # Reset button text to initial state
        self.record_button.setText("Start Listening")
        self.record_button.setEnabled(True)

        # Reset button text to initial state
        self.record_button.setText("Start Listening")
        self.record_button.setEnabled(True)

    def play_audio(self, mp3_url=None, button=None):
        if mp3_url is not None:
            if button is not None:
                if self.current_playing_button is not None:
                    if self.current_playing_button == button:
                        # Toggle play/pause if the same button is pressed
                        if self.is_paused is False:
                            self.media_player.pause()
                            button.setText("▶")
                            self.is_paused = True
                        else:
                            self.media_player.play()
                            button.setText("❚❚")
                            self.is_paused = False
                    else:
                        # Pause the previously playing button
                        self.media_player.pause()
                        self.current_playing_button.setText("▶")
                        self.current_playing_button = button
                        self.media_player.setMedia(QMediaContent(QUrl(mp3_url)))
                        self.media_player.play()
                        button.setText("❚❚")
                        self.is_paused = False
                else:
                    # Play the new audio and set the current button
                    self.current_playing_button = button
                    self.media_player.setMedia(QMediaContent(QUrl.fromLocalFile(mp3_url)))
                    self.media_player.play()
                    button.setText("❚❚")
                    self.is_paused = False
            else:
                self.media_player.setMedia(QMediaContent(QUrl.fromLocalFile(mp3_url)))
                self.media_player.play()
                self.is_paused = False
        else:
            # Stop audio if no URL is provided
            self.media_player.stop()
            if self.current_play_button is not None:
                self.current_play_button.setText("▶")
            self.is_paused = True
            self.current_mp3_url = None
            self.current_playing_button = None

    def set_album_image(self, image_url):
        try:
            # Download the image
            response = requests.get(image_url)
            response.raise_for_status()  # Raise an exception for HTTP errors

            # Create a QPixmap from the image data
            image_data = QBuffer()
            image_data.setData(response.content)
            image_data.open(QIODevice.ReadOnly)
            pixmap = QPixmap()
            pixmap.loadFromData(response.content)

            # Set the pixmap to the label
            self.song_image_label.setPixmap(pixmap.scaled(150, 150, Qt.KeepAspectRatio))
            self.song_image_label.show()

        except Exception as e:
            print(f"Failed to load image: {e}")
            self.song_image_label.setPixmap(QPixmap(self.default_album_image).scaled(150, 150, Qt.KeepAspectRatio))
            self.song_image_label.show()

    def toggle_extra_songs(self):
        if self.extra_songs_widget.isVisible():
            self.extra_songs_widget.hide()
            self.reveal_link.show()  # Show the reveal link again
        else:
            self.extra_songs_widget.show()
            self.reveal_link.hide()  # Hide the reveal link when showing extra songs

    def show_error(self, error_message):
        # Show error message
        self.song_title_label.setText(error_message)
        self.album_artist_label.clear()
        self.release_year_label.clear()

        # Reset button text to initial state
        self.record_button.setText("Start Listening")
        self.record_button.setEnabled(True)  # Re-enable the button

        # Hide extra songs section if it's visible
        self.extra_songs_widget.hide()

    def clear_song_info(self):
        """Clears the song info section."""
        self.song_title_label.clear()
        self.album_artist_label.clear()
        self.release_year_label.clear()
        self.genre_label.clear()  # Add clearing of genre line
        self.duration_label.clear()  # Clear duration label
        self.song_image_label.setPixmap(QPixmap(self.default_album_image).scaled(150, 150, Qt.KeepAspectRatio))
        self.song_image_label.hide()

        # Stop and reset the media player
        self.media_player.stop()
        self.is_paused = True  # Reset pause state
        self.current_mp3_url = None  # Reset the mp3 URL
        self.current_playing_button = None

        # Hide extra songs section if it's visible
        while self.extra_songs_layout.count():
            item = self.extra_songs_layout.takeAt(0)
            widget = item.widget()
            if widget:
                widget.deleteLater()
            else:
                # If it's a layout, delete its children recursively
                sub_layout = item.layout()
                if sub_layout:
                    while sub_layout.count():
                        sub_item = sub_layout.takeAt(0)
                        sub_widget = sub_item.widget()
                        if sub_widget:
                            sub_widget.deleteLater()
                        else:
                            # Recursively clear nested layouts
                            self.clear_extra_songs(sub_layout)
                    sub_layout.deleteLater()

            # Ensure the extra songs section is hidden
        self.extra_songs_widget.setVisible(False)
        self.reveal_link.hide()


if __name__ == '__main__':
    app = QApplication(sys.argv)
    window = ShazamCloneApp()
    window.show()
    sys.exit(app.exec_())
