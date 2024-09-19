from PyQt5.QtCore import QDateTime


class SongMetadata:
    def __init__(self, title="", artistsNames="", category="", duration=0, link="", releaseDate=0, thumbnailM="",
                 mp3url=""):
        self.title = title
        self.artistsNames = artistsNames
        self.category = category
        self.duration = duration
        self.link = link
        self.releaseDate = releaseDate
        self.thumbnailM = thumbnailM
        self.mp3url = mp3url

    def formatted_release_date(self):
        return QDateTime.fromSecsSinceEpoch(self.releaseDate).toString("dd/MM/yyyy")

    def formatted_duration(self):
        duration_seconds = self.duration
        if duration_seconds >= 3600:
            # Format as hh:mm:ss
            return f"{duration_seconds // 3600:02}:{(duration_seconds % 3600) // 60:02}:{duration_seconds % 60:02}"
        else:
            # Format as mm:ss
            return f"{duration_seconds // 60:02}:{duration_seconds % 60:02}"
