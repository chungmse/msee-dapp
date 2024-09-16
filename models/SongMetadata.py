from PyQt5.QtCore import QDateTime


class SongMetadata:
    def __init__(self, title="", artistsNames="", category="", duration=0, link="", releaseDate=0, thumbnailM="", mp3url=""):
        self.title = title
        self.artistsNames = artistsNames
        self.category = category
        self.duration = duration
        self.link = link
        self.releaseDate = releaseDate
        self.thumbnailM = thumbnailM
        self.mp3url = mp3url

    def formatted_release_date(self):
        return QDateTime.fromSecsSinceEpoch(self.releaseDate).toString("dd-MM-yyyy")

    def formatted_duration(self):
        duration_seconds = self.duration
        if duration_seconds >= 3600:
            return f"{duration_seconds // 3600}h {duration_seconds % 3600 // 60}m"
        elif duration_seconds >= 60:
            return f"{duration_seconds // 60}m"
        else:
            return f"{duration_seconds}s"
