# Instructions to run the video scraper

This project includes a Python script (`scraper.py`) to automatically fetch video information from Pornhub. To use it, you need to have Python installed on your system.

## 1. Install Required Libraries

Before running the scraper, you need to install two Python libraries: `requests` and `beautifulsoup4`. Open your command prompt or terminal and run the following commands:

```bash
pip install requests
pip install beautifulsoup4
```

## 2. Run the Scraper

Once the libraries are installed, you can run the scraper. Open your command prompt or terminal, navigate to the project directory (`c:\Users\HP\Desktop\VScode prj\Adultlyf`), and run the following command:

```bash
python scraper.py
```

The script will start scraping the Pornhub homepage, and you will see the titles of the scraped videos in the console. When it's finished, it will create a file named `videos.json` in the same directory. This file contains the video data that the website will use.

## 3. Update the Website

The `index.html` file is set up to read the `videos.json` file and display the videos. If you want to update the videos on your site, simply run the `scraper.py` script again to generate a new `videos.json` file.
