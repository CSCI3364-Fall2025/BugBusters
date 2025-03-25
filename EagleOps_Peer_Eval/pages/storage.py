from django.core.files.storage import Storage

class NullStorage(Storage):
    """
    A storage backend that discards files instead of saving them.
    """

    def _save(self, name, content):
        # Simply return the file name without writing the file
        return name

    def exists(self, name):
        # Always return False so Django thinks the file doesn't already exist
        return False

    def url(self, name):
        # Optionally, return an empty string or a placeholder URL
        return ""
