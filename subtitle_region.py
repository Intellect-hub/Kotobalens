
from PySide6.QtCore import QSettings


class SubtitleRegionManager:
    """
    Saves and loads the subtitle capture region.

    The coordinates are stored locally using QSettings.
    """

    def __init__(self):
        self.settings = QSettings(
            "JapaneseSubtitleHelper",
            "JapaneseSubtitleHelper",
        )

    def save_region(self, left, top, width, height):
        """Save the selected subtitle rectangle."""

        left = int(left)
        top = int(top)
        width = int(width)
        height = int(height)

        if width <= 0 or height <= 0:
            raise ValueError(
                "Subtitle region must have positive width and height."
            )

        self.settings.setValue(
            "subtitle_region/left", left
        )
        self.settings.setValue(
            "subtitle_region/top", top
        )
        self.settings.setValue(
            "subtitle_region/width", width
        )
        self.settings.setValue(
            "subtitle_region/height", height
        )

        self.settings.sync()

        print(
            "Subtitle region saved:",
            left, top, width, height
        )

    def load_region(self):
        """Return saved coordinates, or None if unavailable."""

        keys = [
            "left",
            "top",
            "width",
            "height",
        ]

        values = {}

        for key in keys:
            value = self.settings.value(
                f"subtitle_region/{key}",
                None,
            )

            if value is None:
                return None

            try:
                values[key] = int(value)
            except (TypeError, ValueError):
                return None

        if (
            values["width"] <= 0
            or values["height"] <= 0
        ):
            return None

        return values

    def clear_region(self):
        """Forget the saved subtitle rectangle."""

        self.settings.remove(
            "subtitle_region"
        )
        self.settings.sync()

        print("Saved subtitle region cleared.")

    def has_region(self):
        """Check whether a valid region has been saved."""

        return self.load_region() is not None
