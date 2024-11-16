# DLC-Downloader
DLC Downloader for The Simpsons: Tapped Out. Thank you to [schdub](https://github.com/schdub/dlcsync) for (most) of the code. I decided to modify his, as i want to get this done before Jan. 24 when the game shuts down. 

## Usage
You will need about 200GB of free storage, and [python3](https://www.python.org) installed.
```
python3 dlcDownloader.py
```

## Configuration
If you want to for example change the language of dlcs the script downloads, you can do so at the top of the script.
```
verbose = False        # display some debug messages
lang = [ 'all', 'en' ] # en,fr,it,de,es,ko,zh,cn,pt,ru,tc,da,sv,no,nl,tr,th
tier = [ 'all', '100', 'retina', 'iphone', 'ipad', 'ipad3' ] # 25,50,100,retina,iphone,ipad,ipad3
```
