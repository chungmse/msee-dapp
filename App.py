import os
import sys
import time
import wave
from functools import partial

import requests
import sounddevice as sd
from PyQt5.QtCore import Qt, QThread, pyqtSignal, QBuffer, QIODevice, QUrl, QSize, QPropertyAnimation
from PyQt5.QtGui import QFont, QPalette, QColor, QPixmap, QIcon, QPainter, QPainterPath, QMouseEvent
from PyQt5.QtMultimedia import QMediaContent, QMediaPlayer
from PyQt5.QtSvg import QSvgRenderer
from PyQt5.QtWidgets import QApplication, QWidget, QVBoxLayout, QPushButton, QLabel, QGraphicsDropShadowEffect, \
    QScrollArea, QHBoxLayout, QSpacerItem, QGraphicsOpacityEffect, QStackedLayout

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


class SvgBackgroundWidget(QWidget):
    def __init__(self, svg_path, parent=None):
        super().__init__(parent)
        self.renderer = QSvgRenderer(svg_path, self)
        self.opacity_effect = QGraphicsOpacityEffect(self)
        self.setGraphicsEffect(self.opacity_effect)
        self.opacity_animation = QPropertyAnimation(self.opacity_effect, b"opacity")
        self.opacity_animation.setDuration(300)  # Animation duration in ms
        self.opacity_animation.setStartValue(0)
        self.opacity_animation.setEndValue(1)
        self.setAttribute(Qt.WA_TransparentForMouseEvents, True)

    def paintEvent(self, event):
        painter = QPainter(self)
        self.renderer.render(painter)

    def fade_in(self):
        self.show()
        self.opacity_animation.setDirection(QPropertyAnimation.Forward)
        self.opacity_animation.start()

    def fade_out(self):
        self.opacity_animation.setDirection(QPropertyAnimation.Backward)
        self.opacity_animation.start()


class CircularImageLabel(QLabel):
    def __init__(self, parent=None):
        super(CircularImageLabel, self).__init__(parent)
        self.setFixedSize(150, 150)  # Set the size of the circle

    def setPixmap(self, pixmap):
        # Scale the pixmap to fit the label and keep aspect ratio
        scaled_pixmap = pixmap.scaled(self.size(), Qt.KeepAspectRatioByExpanding, Qt.SmoothTransformation)
        super(CircularImageLabel, self).setPixmap(scaled_pixmap)

    def paintEvent(self, event):
        # Paint the circular image
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)

        # Create a circular clipping path
        path = QPainterPath()
        path.addEllipse(0, 0, self.width(), self.height())
        painter.setClipPath(path)

        # Draw the pixmap
        painter.drawPixmap(0, 0, self.pixmap())


# Create a ClickableWidget subclass
class ClickableWidget(QWidget):
    clicked = pyqtSignal()  # Custom signal

    def __init__(self, parent=None):
        super().__init__(parent)

    def mousePressEvent(self, event: QMouseEvent):
        if event.button() == Qt.LeftButton:
            self.clicked.emit()  # Emit the clicked signal when the widget is clicked


def get_asset_path(relative_path):
    """Return the absolute path to an asset bundled with the app."""
    if hasattr(sys, '_MEIPASS'):
        return os.path.join(sys._MEIPASS, relative_path)
    return os.path.join(os.path.abspath("."), relative_path)


class ShazamCloneApp(QWidget):
    def __init__(self):
        super().__init__()

        # Set up the window
        self.setWindowTitle('Msee')
        self.setGeometry(100, 100, 400, 600)
        self.showMaximized()

        # Set up the background color
        palette = QPalette()
        palette.setColor(QPalette.Window, QColor("#ffffff"))
        self.setPalette(palette)

        # Create the layout for stacking widgets
        stacked_layout = QStackedLayout(self)

        # Main layout to hold non-scrollable and scrollable sections
        main_widget = QWidget(self)
        main_layout_container = QVBoxLayout(main_widget)

        # Create the non-scrollable container for the main button
        self.button_container = QWidget(self)
        button_layout = QVBoxLayout(self.button_container)
        button_layout.setAlignment(Qt.AlignCenter)

        # Create a label for the text above the button
        self.button_text_label = QLabel("Nhấn để Msee...", self)
        self.button_text_label.setFont(QFont("Arial", 24, QFont.Bold))
        self.button_text_label.setStyleSheet("color: #2675b4;")
        self.button_text_label.setAlignment(Qt.AlignCenter)
        button_layout.addWidget(self.button_text_label, alignment=Qt.AlignCenter)

        # Add a spacer to add space between the text and the button
        spacer = QSpacerItem(20, 20)
        button_layout.addItem(spacer)

        # Create the main button with an icon
        self.record_button = QPushButton(self)
        self.record_button.setIcon(QIcon(get_asset_path("assets/music_note_icon.png")))
        self.record_button.setIconSize(QSize(75, 75))  # Adjust size as needed
        self.record_button.setStyleSheet("""
            QPushButton {
                background-color: #2675b4;
                border-radius: 100px;
                height: 200px;
                width: 200px;
                color: #E2E2E2;
            }
            QPushButton:hover {
                background-color: #1a5e9c;
            }
        """)
        shadow_effect = QGraphicsDropShadowEffect()
        shadow_effect.setBlurRadius(30)
        shadow_effect.setOffset(0, 10)
        shadow_effect.setColor(QColor(0, 0, 0, 150))
        self.record_button.setGraphicsEffect(shadow_effect)
        self.record_button.clicked.connect(self.start_listening)
        button_layout.addWidget(self.record_button, alignment=Qt.AlignCenter)

        # Empty space for anim
        self.empty_space = QWidget(self)
        self.empty_space.setFixedSize(200, 200)
        self.empty_space.hide()
        button_layout.addWidget(self.empty_space, alignment=Qt.AlignCenter)

        # Add a label below the button with normal font
        self.below_button_label = QLabel("Đang lắng nghe âm nhạc", self)
        self.below_button_label.setFont(QFont("Arial", 24, QFont.Bold))
        self.below_button_label.setStyleSheet("color: #2675b4;")
        self.below_button_label.setAlignment(Qt.AlignCenter)
        self.below_button_label.hide()
        button_layout.addWidget(self.below_button_label, alignment=Qt.AlignCenter)

        # Add another label below with thinner font
        self.thinner_label = QLabel("Cố gắng giữ im lặng để Msee lắng nghe", self)
        self.thinner_label.setFont(QFont("Arial", 14))
        self.thinner_label.setStyleSheet("color: #2675b4;")
        self.thinner_label.setAlignment(Qt.AlignCenter)
        self.thinner_label.hide()
        button_layout.addWidget(self.thinner_label, alignment=Qt.AlignCenter)

        # Add the non-scrollable button container to the main layout
        main_layout_container.addWidget(self.button_container)

        # Create a sticky header widget
        self.header_widget = QWidget()
        self.header_layout = QVBoxLayout(self.header_widget)
        self.header_layout.setContentsMargins(0, 0, 0, 0)  # Remove margins for the header layout
        self.header_widget.hide()

        # Create the sticky label
        self.sticky_label = QLabel("Msee...", self)
        self.sticky_label.setFont(QFont("Arial", 24, QFont.Bold))
        self.sticky_label.setStyleSheet("background-color: #ffffff; color: #2675b4; padding: 10px;")
        self.sticky_label.setAlignment(Qt.AlignCenter)
        self.header_layout.addWidget(self.sticky_label)

        # Add the header widget to the main layout
        main_layout_container.addWidget(self.header_widget)

        # Scrollable container for song info and extra songs
        self.scroll_area = QScrollArea()
        self.scroll_area.setWidgetResizable(True)
        self.scroll_area.setStyleSheet("background-color: #ffffff; border: none;")
        self.scroll_area.hide()

        # Main scrollable widget that will contain song info and extra songs
        scrollable_widget = QWidget()
        scrollable_layout = QVBoxLayout(scrollable_widget)

        # Create a top-left container for the X button
        x_button_container = QWidget(self)
        x_button_layout = QHBoxLayout(x_button_container)
        x_button_layout.setContentsMargins(0, 0, 0, 0)  # Remove any margins
        x_button_layout.setAlignment(Qt.AlignTop | Qt.AlignLeft)

        # Create the X button
        self.clear_button = QPushButton("✕", self)
        self.clear_button.setFixedSize(30, 30)  # Set a fixed size for the button
        self.clear_button.setStyleSheet("""
            QPushButton {
                background-color: #E2E2E2;
                color: #2675b4;
                border: none;
                font-size: 18px;
                font-weight: bold;
                border-radius: 15px;
            }
            QPushButton:hover {
                background-color: #C0C0C0;
            }
        """)
        self.clear_button.clicked.connect(self.clear_song_info)
        self.clear_button.hide()

        # Add the X button to the layout
        x_button_layout.addWidget(self.clear_button)

        # Add the top-left X button layout to the scrollable layout
        scrollable_layout.addWidget(x_button_container, alignment=Qt.AlignTop | Qt.AlignRight)

        # Song info UI setup
        self.song_info_widget = QWidget(self)
        self.song_info_layout = QVBoxLayout(self.song_info_widget)
        self.song_info_layout.setSpacing(10)
        self.song_info_widget.setStyleSheet("""
            QWidget {
                background: qlineargradient(
                    spread:pad, x1:0, y1:0, x2:1, y2:1,
                    stop:0 #4d8fc3, stop:1 #a4c7e2
                );
                border-radius: 15px;
            }
        """)
        self.song_info_layout.setContentsMargins(20, 20, 20, 20)

        self.song_image_label = CircularImageLabel(self)
        self.default_album_image = get_asset_path("assets/default_album.jpg")
        self.song_image_label.setFixedSize(150, 150)
        self.song_image_label.setPixmap(QPixmap(self.default_album_image))
        self.song_image_label.setAlignment(Qt.AlignCenter)
        self.song_image_label.setStyleSheet("""
            QLabel {
                border: 3px solid white;
                border-radius: 75px;
            }
        """)
        self.song_image_label.hide()
        self.song_info_layout.addWidget(self.song_image_label, alignment=Qt.AlignCenter)

        self.song_title_label = QLabel("", self)
        self.song_title_label.setFont(QFont("Arial", 24, QFont.Bold))
        self.song_title_label.setStyleSheet("color: white; background: none;")
        self.song_title_label.setAlignment(Qt.AlignCenter)
        self.song_info_layout.addWidget(self.song_title_label, alignment=Qt.AlignCenter)

        self.album_artist_label = QLabel("", self)
        self.album_artist_label.setFont(QFont("Arial", 16))
        self.album_artist_label.setStyleSheet("color: white; background: none;")
        self.album_artist_label.setAlignment(Qt.AlignCenter)
        self.song_info_layout.addWidget(self.album_artist_label, alignment=Qt.AlignCenter)

        self.genre_label = QLabel("", self)
        self.genre_label.setFont(QFont("Arial", 14))
        self.genre_label.setStyleSheet("color: white; background: none;")
        self.genre_label.setAlignment(Qt.AlignCenter)
        self.song_info_layout.addWidget(self.genre_label, alignment=Qt.AlignCenter)

        self.duration_label = QLabel("", self)
        self.duration_label.setFont(QFont("Arial", 14))
        self.duration_label.setStyleSheet("color: white; background: none;")
        self.duration_label.setAlignment(Qt.AlignCenter)
        self.song_info_layout.addWidget(self.duration_label, alignment=Qt.AlignCenter)

        self.release_year_label = QLabel("", self)
        self.release_year_label.setFont(QFont("Arial", 14))
        self.release_year_label.setStyleSheet("color: white; background: none;")
        self.release_year_label.setAlignment(Qt.AlignCenter)
        self.song_info_layout.addWidget(self.release_year_label, alignment=Qt.AlignCenter)

        # Add song info widget to the scrollable layout
        scrollable_layout.addWidget(self.song_info_widget, alignment=Qt.AlignCenter)

        # Add clickable label to reveal extra songs (hidden initially)
        self.reveal_link = QLabel('Không phải bài hát bạn đang tìm kiếm?', self)
        self.reveal_link.setStyleSheet("""
            color: #2675b4;
            text-decoration: underline;
            font-size: 12px;
        """)
        self.reveal_link.hide()  # Hide the link at startup
        scrollable_layout.addWidget(self.reveal_link, alignment=Qt.AlignCenter)

        # Button to toggle extra songs (placed below the reveal_link)
        self.toggle_extra_songs_button = QPushButton("Tìm kiếm các bài hát khác", self)
        self.toggle_extra_songs_button.setStyleSheet("""
            QPushButton {
                background-color: #2675b4;
                color: white;
                border: none;
                font-size: 14px;
                padding: 10px;
                border-radius: 5px;
            }
            QPushButton:hover {
                background-color: #1a5e8a;
            }
        """)
        self.toggle_extra_songs_button.clicked.connect(self.toggle_extra_songs)  # Connect to toggle method
        self.toggle_extra_songs_button.hide()  # Hide the button at startup
        scrollable_layout.addWidget(self.toggle_extra_songs_button, alignment=Qt.AlignCenter)

        # Extra songs container (hidden initially)
        self.extra_songs_widget = QWidget(self)
        self.extra_songs_layout = QVBoxLayout(self.extra_songs_widget)
        self.extra_songs_widget.setStyleSheet("background-color: #ffffff;")
        self.extra_songs_widget.hide()
        self.current_playing_button = None

        # Add the extra songs widget to the scrollable layout
        scrollable_layout.addWidget(self.extra_songs_widget, alignment=Qt.AlignCenter)

        # Set the scrollable widget inside the scroll area
        self.scroll_area.setWidget(scrollable_widget)

        # Add the scrollable area to the main layout
        main_layout_container.addWidget(self.scroll_area)

        # Set the layout for the main window
        self.setLayout(main_layout_container)

        # Add to stacked layout
        stacked_layout.addWidget(main_widget)

        # Ensure the pulse container is in the background
        stacked_layout.setCurrentIndex(1)

        # Initialize QMediaPlayer
        self.media_player = QMediaPlayer()

        # Initialize variables to handle audio state
        self.is_paused = True
        self.current_mp3_url = None

        # Audio-related variables
        self.recorded_audio = None

        # Create threads
        self.audio_recorder_thread = AudioRecorderThread()
        self.processing_thread = None

        # Connect signals
        self.audio_recorder_thread.recording_done.connect(self.start_processing)
        self.audio_recorder_thread.error_occurred.connect(self.show_error)

    def start_listening(self):
        # Clear previous song info
        self.clear_song_info()

        # Update UI to show listening state
        self.button_text_label.setText("Msee...")
        self.record_button.hide()
        self.below_button_label.show()
        self.thinner_label.show()

        # Start the recording thread
        self.audio_recorder_thread.start()

    def start_processing(self, audio_file_path):
        # Update UI to show processing state
        self.below_button_label.setText("Đang nhận diện bài hát")
        self.thinner_label.setText("Vui lòng chờ trong giây lát...")

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

            # Hide button container
            self.button_container.hide()
            self.empty_space.hide()
            self.record_button.show()

            # Show scrollable container
            self.header_widget.show()
            self.scroll_area.show()

            # Show the clear button
            self.clear_button.show()

            # Update UI with the song metadata
            self.song_title_label.setText(song_metadata.title)
            self.album_artist_label.setText(f"{song_metadata.artistsNames}")
            self.genre_label.setText(f"Thể loại: {song_metadata.category}")
            self.duration_label.setText(f"Thời lượng: {song_metadata.formatted_duration()}")
            self.release_year_label.setText(f"Ngày phát hành: {song_metadata.formatted_release_date()}")

            # Download and set the album image
            self.set_album_image(song_metadata.thumbnailM)

            # Set the play button only if mp3_url is available
            self.current_mp3_url = song_metadata.mp3url
            self.play_audio(song_metadata.mp3url)

            # Check if extra songs are available
            if len(response_data.get("list_result", [])) > 1:
                # Show the reveal link
                self.reveal_link.show()
                self.toggle_extra_songs_button.show()

                # Populate the extra songs section
                list_result = response_data["list_result"]

                # Create the header label for the extra songs section
                extra_songs_header = QLabel("Tất cả kết quả nhận diện:", self)
                extra_songs_header.setFont(QFont("Arial", 16, QFont.Bold))
                extra_songs_header.setStyleSheet("color: #2675b4; padding-bottom: 10px;")
                extra_songs_header.setAlignment(Qt.AlignLeft)
                self.extra_songs_layout.addWidget(extra_songs_header)

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
                    container_widget = ClickableWidget(self)
                    container_widget.setStyleSheet("""
                            QWidget {
                                background-color: #e9f1fc;
                                border-radius: 15px;
                            }
                        """)
                    h_layout = QHBoxLayout(container_widget)
                    h_layout.setContentsMargins(10, 10, 10, 10)

                    # Download the image
                    response = requests.get(song.thumbnailM)
                    response.raise_for_status()  # Raise an exception for HTTP errors

                    # Create a QPixmap from the image data
                    image_data = QBuffer()
                    image_data.setData(response.content)
                    image_data.open(QIODevice.ReadOnly)
                    pixmap = QPixmap()
                    pixmap.loadFromData(response.content)

                    # Album image on the left
                    album_image_label = CircularImageLabel(self)
                    album_image_label.setPixmap(QPixmap(pixmap))
                    album_image_label.setFixedSize(80, 80)
                    album_image_label.setAlignment(Qt.AlignCenter)
                    album_image_label.setStyleSheet("""
                            QLabel {
                                border-radius: 40px;
                            }
                        """)
                    h_layout.addWidget(album_image_label)

                    # Text on the right
                    text_layout = QVBoxLayout()
                    text_layout.setContentsMargins(0, 0, 0, 0)

                    title_label = QLabel(song.title, self)
                    title_label.setFont(QFont("Arial", 16, QFont.Bold))
                    title_label.setStyleSheet("color: #2675b4; background: transparent;")
                    text_layout.addWidget(title_label)

                    artist_label = QLabel(song.artistsNames, self)
                    artist_label.setFont(QFont("Arial", 14))
                    artist_label.setStyleSheet("color: #6c8fc2; background: transparent;")  # Muted color
                    text_layout.addWidget(artist_label)

                    duration_label = QLabel(song.formatted_duration(), self)
                    duration_label.setFont(QFont("Arial", 14))
                    duration_label.setStyleSheet("color: #6c8fc2; background: transparent;")  # Muted color
                    text_layout.addWidget(duration_label)

                    h_layout.addLayout(text_layout)

                    # Add play button beside each song
                    play_button = QPushButton("▶", self)
                    play_button.setFixedSize(40, 40)
                    play_button.setStyleSheet("""\
                            QPushButton {
                                background-color: #2675b4;
                                border-radius: 20px; /* Half of the height/width */
                                color: #ffffff;
                                font-size: 18px;
                            }
                            QPushButton:hover {
                                background-color: #1a5e9c;
                            }
                        """)
                    play_button.hide()
                    container_widget.clicked.connect(partial(self.play_audio, song.mp3url, play_button))
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
            self.song_title_label.setText("Không tìm thấy bài hát")
            self.album_artist_label.clear()
            self.release_year_label.clear()
            self.duration_label.clear()

        # Reset button text to initial state
        self.button_text_label.setText("Nhấn để Msee")
        self.record_button.show()
        self.below_button_label.setText("Đang lắng nghe âm nhạc")
        self.below_button_label.hide()
        self.thinner_label.setText("Cố gắng giữ im lặng để Msee lắng nghe")
        self.thinner_label.hide()

    def play_audio(self, mp3_url=None, button=None):
        if mp3_url is not None:
            if button is not None:
                if self.current_playing_button is not None:
                    if self.current_playing_button == button:
                        # Toggle play/pause if the same button is pressed
                        if self.is_paused is False:
                            self.media_player.pause()
                            button.hide()
                            self.is_paused = True
                        else:
                            self.media_player.play()
                            button.show()
                            self.is_paused = False
                    else:
                        # Pause the previously playing button
                        self.media_player.pause()
                        self.current_playing_button.hide()
                        self.current_playing_button = button
                        self.media_player.setMedia(QMediaContent(QUrl(mp3_url)))
                        self.media_player.play()
                        button.show()
                        self.is_paused = False
                else:
                    # Play the new audio and set the current button
                    self.current_playing_button = button
                    self.media_player.setMedia(QMediaContent(QUrl.fromLocalFile(mp3_url)))
                    self.media_player.play()
                    button.show()
                    self.is_paused = False
            else:
                self.media_player.setMedia(QMediaContent(QUrl.fromLocalFile(mp3_url)))
                self.media_player.play()
                self.is_paused = False
        else:
            # Stop audio if no URL is provided
            self.media_player.stop()
            if self.current_play_button is not None:
                self.current_play_button.hide()
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
            self.song_image_label.setPixmap(pixmap)
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

    def clear_song_info(self):
        # Hide clear button
        self.clear_button.hide()

        # Clears the song info section
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

        # Hide scrollable area
        self.scroll_area.hide()
        self.header_widget.hide()

        # Show button container
        self.button_container.show()

        # Reset button text to initial state
        self.button_text_label.setText("Nhấn để Msee")
        self.record_button.show()
        self.below_button_label.setText("Đang lắng nghe âm nhạc")
        self.below_button_label.hide()
        self.thinner_label.setText("Cố gắng giữ im lặng để Msee lắng nghe")
        self.thinner_label.hide()

    def show_error(self, error_message):
        # Show error message
        self.song_title_label.setText(error_message)
        self.album_artist_label.clear()
        self.release_year_label.clear()

        # Reset button text to initial state
        self.button_text_label.setText("Nhấn để Msee")
        self.record_button.show()
        self.below_button_label.setText("Đang lắng nghe âm nhạc")
        self.below_button_label.hide()
        self.thinner_label.setText("Cố gắng giữ im lặng để Msee lắng nghe")
        self.thinner_label.hide()

        # Hide extra songs section if it's visible
        self.extra_songs_widget.hide()


if __name__ == '__main__':
    app = QApplication(sys.argv)
    window = ShazamCloneApp()
    window.show()
    sys.exit(app.exec_())
