# Suchkriterien — hier zentral anpassen, gilt für alle Scraper

# Mindest-Wohnfläche in m²
MIN_LIVING_AREA_M2 = 200

# Mindest-Grundstücksgröße in m²
MIN_PLOT_SIZE_M2 = 2500

# Maximale Fahrzeit ab Wien (Direktzug, Minuten)
MAX_TRAIN_MINUTES = 90

# Maximale Fahrradzeit vom Bahnhof (Minuten)
MAX_BIKE_MINUTES = 25

# Suchbegriffe für Immobilien-Plattformen
SEARCH_KEYWORDS = [
    "Bauernhaus",
    "Bauernhof",
    "Landhaus",
    "Landgut",
    "Gehöft",
    "Schloss",
    "Herrenhaus",
    "Reiterhof",
    "Weingut",
    "Gut kaufen",
    "Mehrparteienhaus Land",
]

# Zielgruppe (für spätere Beschreibungsfilter)
TARGET_PARTIES = (2, 5)       # min/max Parteien
TARGET_AGE = "Anfang 30"      # Pärchen mit eventuellem Kinderwunsch

# Zustand: alle akzeptiert (schlüsselfertig, kosmetisch, Vollrenovierung)
ACCEPTED_CONDITIONS = ["schlüsselfertig", "renovierungsbedürftig", "vollrenovierung"]
