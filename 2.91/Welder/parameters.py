
NAME="Welder"
DECAL_SUFFIX="_decal"
PROXY_SUFFIX="_proxy"
WELD_FILE="weld.blend"
INTERSECTION_COLLECTION_NAME="TemporaryIntersectors"

thisdict = {
  "brand": "Ford",
  "model": "Mustang",
  "year": 1964
}

class Weld:
    def __init__(self, name, iconpath):
        self.name = name
        self.iconpath = iconpath
