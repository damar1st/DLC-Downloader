import xml.etree.ElementTree as ET
from requests import get, exceptions
from colorama import Fore
from time import sleep
import os, io, zipfile, zlib
from concurrent.futures import ThreadPoolExecutor


OUT_DIR = "./dlc"
LANGUAGE = ["en", "fr", "it", "de", "es", "ko", "zh", "cn", "pt", "ru", "tc", "da", "sv", "no", "nl", "tr", "th"]
TIER = ["all", "25", "50", "100", "retina", "iphone", "ipad", "ipad3", "mp3", "caf", "wav"]
ALL_LANGUAGES = True
ALL_TIERS = True
BASE_URL = "http://oct2018-4-35-0-uam5h44a.tstodlc.eamobile.com/netstorage/gameasset/direct/simpsons/"
DOWNLOAD_QUEUE = []  # [Url, Dateiname, Ordner, CRC32]
THREADS = 10  #


def log(severity: int, message: str):
    if severity == 0:
        print(Fore.BLUE + "[i] " + Fore.WHITE + message)
    elif severity == 1:
        print(Fore.YELLOW + "[!] " + Fore.WHITE + message)
    elif severity == 2:
        print(Fore.RED + "[!] " + Fore.WHITE + message)
    else:
        print(Fore.WHITE + message)


def calculate_crc32_from_zip(filepath: str) -> int:
    """Berechnet den CRC32-Wert der ersten Datei innerhalb einer ZIP-Datei."""
    if not os.path.exists(filepath):
        return None

    with zipfile.ZipFile(filepath, 'r') as z:
        first_file = z.infolist()[0]
        with z.open(first_file) as file:
            data = file.read()
            crc32_value = zlib.crc32(data) & 0xFFFFFFFF
    return crc32_value


def downloadFile(args):
    """Lädt eine Datei herunter und überprüft CRC32."""
    url, filename, folder, expected_crc32 = args
    filepath = os.path.join(OUT_DIR, folder, filename)
    os.makedirs(os.path.join(OUT_DIR, folder), exist_ok=True)

    headers = {'User-Agent': 'Mozilla/5.0 (compatible; Python Script)'}
    try:
        response = get(url, headers=headers, stream=True, timeout=30)
        if response.status_code != 200:
            log(1, f"Fehlerhafte Antwort ({response.status_code}). Übersprungen... ({url})")
            return None

        log(0, f"Lade {filename} herunter...")
        with open(filepath, "wb") as outFile:
            for chunk in response.iter_content(chunk_size=8192):
                if chunk:
                    outFile.write(chunk)

        # Überprüfe den CRC32-Wert
        if expected_crc32:
            current_crc32 = calculate_crc32_from_zip(filepath)
            log(0, f"Expected CRC32: {expected_crc32}, Current CRC32: {current_crc32}")
            if int(expected_crc32) != current_crc32:
                log(2, f"CRC32 der ersten Datei in {filename} stimmt nicht überein. Datei wird verworfen.")
                os.remove(filepath)
                return None

        log(0, f"Heruntergeladen {filename} ({os.path.getsize(filepath)} Bytes).")
        return filepath

    except (exceptions.ChunkedEncodingError, exceptions.ConnectionError, exceptions.IncompleteRead) as e:
        log(1, f"Verbindungsfehler: {e}. Datei {filename} wird übersprungen.")
        return None
    except exceptions.RequestException as e:
        log(2, f"RequestException: {e}")
        return None


def getDLCIndexXml(url: str, filename: str):
    filepath = downloadFile((url, filename, "dlc", None))
    if not filepath:
        return None

    with zipfile.ZipFile(filepath, 'r') as z:
        data = z.read(z.infolist()[0])
        return data


def getDLCIndexes():
    log(0, "Lade DLC-Indexe...")
    try:
        os.makedirs(os.path.join(OUT_DIR, "dlc"), exist_ok=True)
        masterIndexData = getDLCIndexXml(BASE_URL + "dlc/DLCIndex.zip", "DLCIndex.zip")
        if not masterIndexData:
            return []

        tree = ET.fromstring(masterIndexData)
        lst = tree.findall("./IndexFile")
        return [item.get("index").replace(":", "/") for item in lst]

    except ET.ParseError as e:
        log(2, f"Fehler beim Parsen von XML: {e}")
        return []


class DLCIndexParser:
    def __init__(self):
        self.tier = ""
        self.FileName = ""
        self.Language = ""
        self.CRC32 = ""

    def start(self, tag, attrs):
        if tag == "Package":
            self.tier = attrs.get("tier", "")
            self.Language = ""
            self.FileName = ""
            self.CRC32 = ""

        elif tag == "FileName":
            self.FileName = attrs.get("val", "")
        elif tag == "Language":
            self.Language = attrs.get("val", "")
        elif tag == "IndexFileCRC":
            self.CRC32 = attrs.get("val", "")

    def end(self, tag):
        if tag == "Package":
            if not self.tier or not self.Language or not self.FileName:
                return

            if not ALL_LANGUAGES and self.Language not in LANGUAGE:
                return
            if not ALL_TIERS and self.tier not in TIER:
                return

            DOWNLOAD_QUEUE.append([
                BASE_URL + self.FileName.replace(":", "/"),
                self.FileName.split(":")[-1],
                self.FileName.split(":")[0],
                self.CRC32
            ])

    def data(self, data):
        pass

    def close(self):
        pass


def check_files():
    """Überprüft, welche Dateien vorhanden sind und deren CRC korrekt ist."""
    to_download = []
    for item in DOWNLOAD_QUEUE:
        url, filename, folder, expected_crc32 = item
        filepath = os.path.join(OUT_DIR, folder, filename)

        if os.path.exists(filepath):
            log(0, f"Überprüfe CRC32 der ersten Datei in {filename}...")
            current_crc32 = calculate_crc32_from_zip(filepath)
            if expected_crc32:
                log(0, f"Expected CRC32: {expected_crc32}, Current CRC32: {current_crc32}")
                if int(expected_crc32) == current_crc32:
                    log(0, f"ZIP-Datei {filename} ist korrekt vorhanden. Übersprungen.")
                    continue
                else:
                    log(1, f"CRC32 der ersten Datei in {filename} stimmt nicht überein. Markiere zum erneuten Download.")
        else:
            log(0, f"Datei {filename} fehlt. Markiere zum Download.")

        # Datei wird zum Download markiert
        to_download.append(item)
    return to_download


def download_files(to_download):
    """Lädt nur die markierten Dateien herunter."""
    log(0, f"Starte Downloads für {len(to_download)} Dateien...")
    with ThreadPoolExecutor(max_workers=THREADS) as executor:
        executor.map(downloadFile, to_download)

    log(0, "Alle Downloads abgeschlossen.")


if __name__ == "__main__":
    indexes = getDLCIndexes()

    # DLC-URLs verarbeiten
    for index in indexes:
        try:
            index_filename = index.split("/")[-1]
            dlcIndexXmlData = getDLCIndexXml(BASE_URL + index, index_filename)
            if not dlcIndexXmlData:
                continue

            parser = ET.XMLParser(target=DLCIndexParser())
            parser.feed(dlcIndexXmlData.decode('utf-8'))
            parser.close()

            log(0, f"Verarbeitet {index}")
        except ET.ParseError as e:
            log(2, f"Fehler beim Parsen von XML für Index {index}: {e}")

    # Phase 1: Überprüfen der Dateien
    log(0, "Starte Überprüfung der Dateien...")
    to_download = check_files()

    # Phase 2: Herunterladen der fehlenden oder ungültigen Dateien
    download_files(to_download)
