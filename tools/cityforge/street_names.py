"""Street names for Port Halden from names/modern_pioneers_500.md, written in each district's style.

    names = StreetNamer("tools/cityforge/names/modern_pioneers_500.md")
    names.take("turkish", "arterial")   -> "Sabiha Gokcen Caddesi"
    names.take("british", "local")      -> "Faraday Street"

Pools: the Turkish pioneers (parts 1-2) name the Turkish quarter and half of the mixed districts;
the international figures are grouped by where they worked (British, continental European,
Asian, American) and named in the local style: "Rue Louis Pasteur", "Max-Planck-Strasse",
"Via Galileo Galilei", "Yukawa-dori", "Raman-ro", "Newton Road". Every name is used once; a
name the file repeats (it lists a few twice) is used only once.
"""
import re

EUROPEAN_LANG = {
    "fr": ["Marie Curie", "Louis Pasteur", "Antoine Lavoisier", "Jean Piaget", "Henri Poincare", "Louis de Broglie", "Georges Cuvier",
           "Alexander Grothendieck", "Emmanuelle Charpentier", "Georges Lemaitre"],
    "it": ["Galileo Galilei", "Enrico Fermi"],
    "de": ["Albert Einstein", "Max Planck", "Robert Koch", "Johannes Kepler", "Sigmund Freud", "Carl Jung", "Kurt Godel", "Werner Heisenberg",
           "Erwin Schrodinger", "Max Born", "Wolfgang Pauli", "David Hilbert", "Lise Meitner", "Otto Hahn", "Fritz Haber", "Carl Bosch",
           "Gregor Mendel", "Nikola Tesla", "Niels Bohr", "Nicolaus Copernicus", "Alfred Nobel", "Linus Torvalds", "Antoni van Leeuwenhoek",
           "Andreas Vesalius", "Carl Linnaeus", "Dmitri Mendeleev", "Konstantin Tsiolkovsky", "Sergei Korolev", "Yuri Gagarin", "Valentina Tereshkova"],
}
BRITISH = ["Isaac Newton", "Charles Darwin", "Alan Turing", "Ada Lovelace", "Rosalind Franklin", "Stephen Hawking", "Ernest Rutherford",
           "Alexander Fleming", "Edward Jenner", "James Clerk Maxwell", "Michael Faraday", "Paul Dirac", "Robert Boyle", "Michael Atiyah",
           "Karl Pearson", "Ronald Fisher", "Tim Berners Lee", "Francis Crick", "Arthur Eddington", "Fred Hoyle", "Jocelyn Bell Burnell",
           "Robert Hooke", "William Harvey", "Charles Lyell", "Alfred Russel Wallace", "Richard Dawkins", "Jane Goodall", "Mary Leakey",
           "Louis Leakey", "Alexander Graham Bell"]
ASIAN = ["Hideki Yukawa", "Chien Shiung Wu", "Tu Youyou", "Satyendra Nath Bose", "C V Raman", "Subrahmanyan Chandrasekhar", "Homi Bhabha",
         "Srinivasa Ramanujan"]
BRITISH_LOCAL = ["Street", "Lane", "Close", "Crescent", "Gardens", "Grove", "Terrace", "Place"]


def surname(full):
    parts = full.split()
    if len(parts) >= 3 and parts[-2].lower() in ("de", "van", "von", "bell"):
        return " ".join(parts[-2:])
    return parts[-1]


class StreetNamer:
    def __init__(self, path):
        text = open(path, encoding="utf-8").read()
        part3 = text.index("## Part 3")
        turkish, world, seen = [], [], set()
        for m in re.finditer(r"^\| \*\*(.+?)\*\* \|", text, re.M):
            name = m.group(1).strip()
            if name in seen: continue
            seen.add(name)
            (turkish if m.start() < part3 else world).append(name)
        european = {n: lang for lang, names in EUROPEAN_LANG.items() for n in names}
        self.pools = {
            "turkish": [n for n in turkish],
            "european": [n for n in world if n in european],
            "british": [n for n in world if n in BRITISH],
            "asian": [n for n in world if n in ASIAN],
            "world": [n for n in world if n not in european and n not in BRITISH and n not in ASIAN],
        }
        self.lang = european
        self.used = set()
        self.counter = 0

    def _next(self, pools):
        for pool in pools:
            for n in self.pools[pool]:
                if n not in self.used:
                    self.used.add(n)
                    return n, pool
        self.counter += 1
        return "Pioneer %d" % self.counter, "world"

    def take(self, culture, cls):
        """A new street name for a road of class cls ("arterial", "boulevard", "local", "downtown") in a district."""
        major = cls in ("arterial", "boulevard")
        if culture == "turkish":
            n, _ = self._next(["turkish"])
            return "%s %s" % (n, "Bulvari" if cls == "boulevard" else "Caddesi" if major else "Sokak")
        if culture == "british":
            n, _ = self._next(["british", "world"])
            s = surname(n)
            return "%s %s" % (s, "Road" if major else BRITISH_LOCAL[self.counter_for(s) % len(BRITISH_LOCAL)])
        if culture == "european":
            n, pool = self._next(["european", "world"])
            lang = self.lang.get(n, "de")
            if lang == "fr": return ("Avenue %s" if major else "Rue %s") % n
            if lang == "it": return ("Viale %s" if major else "Via %s") % n
            return "%s-%s" % (n.replace(" ", "-"), "Allee" if major else "Strasse")
        if culture == "japanese":
            n, _ = self._next(["asian", "world"])
            return "%s-%s" % (surname(n), "Odori" if major else "dori")
        if culture == "korean":
            n, _ = self._next(["asian", "world"])
            return "%s-%s" % (surname(n).replace(" ", ""), "daero" if major else "ro")
        # mixed (and downtown): Turkish and world pioneers alternate, in English
        n, _ = self._next(["turkish", "world"] if self.counter_for(culture) % 2 == 0 else ["world", "turkish"])
        return "%s %s" % (n, {"arterial": "Avenue", "boulevard": "Boulevard", "downtown": "Street"}.get(cls, "Street"))

    def counter_for(self, key):
        self.counter += 1
        return self.counter
