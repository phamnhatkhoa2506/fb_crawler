from manager import ScrapingManager
from data import read_urls, save_data

if __name__ == '__main__':
    URLs = read_urls('urls.txt')

    scraping_manager = ScrapingManager(
        ['start-maximized'],
        [("prefs", {"profile.default_content_setting_values.notifications": 2})],
        num_workers=1,
        logging_file=None
    )

    scraping_manager.start_drivers()
    scraping_manager.start_exceptional_drivers()

    data = scraping_manager.scrape(
        URLs,
        is_scraping_general_info=True,
        is_scraping_about_tab=True
    )

    save_data(data, 'data.json')