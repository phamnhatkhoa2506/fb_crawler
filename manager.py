import time
import threading
import queue
import logging 
import datetime
import re

from typing import List, Dict, Any, Optional
from concurrent.futures import ThreadPoolExecutor
from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import (
    NoSuchElementException, 
    ElementClickInterceptedException, 
    NoSuchWindowException,
    NoSuchAttributeException,
    JavascriptException
)
from webdriver_manager.chrome import ChromeDriverManager
from bs4 import BeautifulSoup

class ScrapingManager(object):
    '''
        An object that manages the scraping of youtube channel information, 
        navigating and process exceptions
    '''

    FACEBOOK_URL = "https://www.facebook.com/"
    USERNAME = '0987655384'
    PASSWORD = 'vonuhuyentran1202'

    xpaths = {
        'login_form_path': '//form[@class="_9vtf"]',
        'username_input_path': '//input[@type="text"]',
        'password_input_path': '//input[@type="password"]',
        'login_button_path': '//button[@name="login"]',
        'meta_data_element': '//meta[@name="description"]',
        'avatar_element_path': '/html/body/div[1]/div/div[1]/div/div[3]/div/div/div[1]/div[1]/div/div/div[1]/div[2]/div/div/div/div[1]/div/a/div/svg/g/image',
        'beside_avt_container': '//div[@class="x9f619 x1n2onr6 x1ja2u2z x78zum5 xdt5ytf x1iyjqo2 x2lwn1j"]',
        'page_name_element_path': '//div[@class="x1e56ztr x1xmf6yo"]/span/h1',
        'close_button_path': '//div[@class="x92rtbv x10l6tqk x1tk7jg1 x1vjfegm"]',
        'about_tab_element_path': '/html/body/div[1]/div/div[1]/div/div[3]/div/div/div[1]/div[1]/div/div/div[3]/div/div/div/div[1]/div/div/div[1]/div/div/div/div/div/div/a[2]',
        'contact_and_basic_info_elements_path': '/html/body/div[1]/div/div[1]/div/div[3]/div/div/div[1]/div[1]/div/div/div[4]/div/div/div/div[1]/div/div/div/div/div[2]/div/div/div/div',
        'intro_description_element_path': '/html/body/div[1]/div/div[1]/div/div[3]/div/div/div[1]/div[1]/div/div/div[4]/div[2]/div/div[1]/div[2]/div/div[1]/div/div/div/div/div[2]/div[1]/div/div/span',
    }
    
    def __init__(
        self, 
        chrome_options: List[str],
        experiment_options: List[str],
        num_workers: int = 5,
        num_exception_workers: int = 1,
        logging_file: Optional[str] = 'logging.txt'
    ) -> None:
        '''
            Initialize the scraping manager

            Params
                chrome_options (list[str]): list of chrome options
                num_workers (int): number of drivers to work
                num_exception_workers (int): number of drivers to handling exception activities
                is_logging (bool): decide whether logging is implemented
                logginf_file (str or None): file to save the logging, just obtained when is_logging = True. If logging_file is none, the logging will be display in the terminal
        '''

        if logging_file is not None:
            logging.basicConfig(filename=logging_file, level=logging.INFO)
        else:
            logging.basicConfig(level=logging.INFO)

        # Add chrome options
        self.__chrome_options = webdriver.ChromeOptions()
        for option in chrome_options:
            self.__chrome_options.add_argument(option)
        for option in experiment_options:
            self.__chrome_options.add_experimental_option(*option)

        # Check value
        if num_workers <= 0 or num_workers >= 8:
            raise ValueError("Number of workers must be positive and smaller than 8")
        if num_exception_workers <= 0 or num_exception_workers >= 5:
            raise ValueError("Number of exceptional workers must be positive and smaller than 5")
        
        # Initialize the drivers and lock 
        self.__lock = threading.Lock() # Lock for race conditions
        self.__driver_queue = queue.Queue() # Queue to store the drivers   
        self.__exception_driver_queue = queue.Queue() # Queue to store the drivers for exception handling

        # Attributes
        self.__num_workers = num_workers
        self.__num_exception_workers = num_exception_workers
        self.__kols: List[Dict[str, Any]] = [] # List of dictionary containing channel information
        self.__is_logged_in = False

    def __scrape_general_url(
        self, 
        driver: webdriver.Chrome,
        kol: Dict[str, Any]
    ) -> Dict[str, Any]:
        '''
            Scrape the general infomation

            Params:
                driver (Chrome): current driver
                kol (dict): dictionary of kol information

            Returns:
                Dictionary of kol infomation after added
        '''

        kol['introDescription'] = ""

        try:
            # Waiting for page loaded
            time.sleep(4)

            '''Head Part'''
            # Get metadata if can access the page without login
            meta_data_element = driver.find_elements(
                By.XPATH,
                self.xpaths['meta_data_element']
            )
            if meta_data_element:
                try:
                    content = meta_data_element[0].get_attribute('content')
                    pattern = r"[\d,]+(?:\.\d+)?\s+(?:likes|talking about)"
                    matches = re.findall(pattern, content)
                
                    if len(matches) > 0:
                        likes_content = matches[0].strip().split() # Get likes
                        talking_about_content = matches[1].strip().split() # Get talking about

                        kol[likes_content[1]] = likes_content[0]
                        kol['talkingAbout'] = talking_about_content[0]
                except NoSuchAttributeException as e:
                    logging.error(e.msg)
            else:
                kol['talkingAbout'] = None   
            
            '''Body Part 1'''
            # Get the avatar url
            try:
                html = driver.page_source
                soup = BeautifulSoup(html, 'html.parser')

                avt_element = soup.find('image') 
                kol["avatarUrl"] = avt_element.attrs["xlink:href"] # Avatar link

                poster_element = soup.find('img', {'data-imgperflogname': 'profileCoverPhoto'})
                kol["profileAvatarUrl"] = poster_element.attrs["src"] # Poster avatar link

            except NoSuchElementException as e:
                logging.info(e.msg)

            # Get the page name
            try:
                beside_avt_container = driver.find_element(
                    By.XPATH, 
                    self.xpaths['beside_avt_container']
                )
            except NoSuchElementException as e:
                logging.info(e.msg)

            try:
                page_name_element = beside_avt_container.find_element(
                    By.XPATH,
                    self.xpaths['page_name_element_path']
                )
                kol['pageName'] = page_name_element.text
            except NoSuchElementException as e:
                logging.info(e.msg)

            # Get likes, followers, followings
            lff_element = beside_avt_container.find_elements(
                By.TAG_NAME,
                'a'
            )
            for a_tag in lff_element:
                a_content = a_tag.text.split()
                kol[a_content[1]] = a_content[0]

            # Get intro description
            try:
                intro_element = driver.find_element(
                    By.XPATH,
                    self.xpaths['intro_description_element_path']
                )
                kol['introDescription'] = intro_element.text
            except NoSuchElementException as e:
                logging.info(e.msg)

            # Check if key not in kol, set following with null value
            for key in ['following', 'followers', 'likes', 'talkingAbout']:
                if key not in kol:
                    kol[key] = None

        except NoSuchElementException as e:
            logging.info("Element Error: " + e.msg)
        except Exception as e:
            print(e)

        return kol
    
    def __scrape_contact_and_basic_info(
        self,
        driver: webdriver.Chrome,
        index: int,
    ):
        '''
            Scrape the contact and basic info in about tab

            Params:
                driver (Chrome): current driver
                index (int): index of kol dictionary in list

            Return:
                Dictionary of kol infomation
        '''

        try:
            # Get contact and basic info element
            contact_and_basic_info_elements = driver.find_elements(
                By.XPATH,
                self.xpaths['contact_and_basic_info_elements_path']
            )
            for j, contact_and_basic_info_element in enumerate(contact_and_basic_info_elements):
                print(j)
                try:
                    span_tag = contact_and_basic_info_element.find_element(
                        By.XPATH,
                        'div/div[1]/div/h2/span'
                    )
                except NoSuchElementException as e:
                    logging.info(e.msg)
                    continue

                print(span_tag.text.lower())
                match span_tag.text.lower():
                    case 'categories': # Get categories tags
                        try:
                            categories_element = contact_and_basic_info_element.find_element(
                                By.XPATH,
                                '//div[@class="xat24cr"]'
                            )
                            print(f"Categories: {categories_element.text}")
                            self.__kols[index]["categories"] = categories_element.text
                        except NoSuchElementException as e:
                            logging.info(e.msg)

                    case 'contact info': # Get contact info tags
                        div_elements = contact_and_basic_info_element.find_elements(
                            By.XPATH,
                            'div/div'
                        )[1:]
                        print(f"Div elements: {len(div_elements)}")
                        for k, div_element in enumerate(div_elements):
                            span_elements = div_element.find_elements(
                                By.TAG_NAME,
                                'span'
                            )
                            print(f"Span: {len(span_elements)}")
                            if span_elements[1].text != "":
                                print(span_elements[1].text.lower(), span_elements[0].text)
                                self.__kols[index][span_elements[1].text.lower()] = span_elements[0].text
                            else:
                                print(f"contactInfo{index + 1}", span_elements[0].text)
                                self.__kols[index][f"contactInfo{k + 1}"] = span_elements[0].text

                    case 'websites and social links': # Get website and social links
                        # Get website links
                        try:
                            website_part = contact_and_basic_info_element.find_element(
                                By.XPATH,
                                'div/div[2]/div/div/div[2]/ul'
                            )
                            
                            website_list = website_part.find_elements(
                                By.TAG_NAME,
                                'li'
                            )
                            print(f"Website list: {len(website_list)}")
                            for website in website_list:
                                span_elements = website.find_elements(
                                    By.TAG_NAME,
                                    'span'
                                )
                                print(span_elements[1].text.lower(), span_elements[0].text)
                                self.__kols[index][span_elements[1].text.lower()].append(span_elements[0].text)
                        except NoSuchElementException as e:
                            logging.info(e.msg)

                        # Get social links
                        social_list_elements = contact_and_basic_info_element.find_elements(
                            By.XPATH,
                            'div/div[3]/div/div/div'
                        )
                        print(f"Social list: {social_list_elements}")
                        for social_list_element in social_list_elements:
                            social_elements = social_list_element.find_elements(
                                By.TAG_NAME,
                                'li'
                            )
                            for social_element in social_elements:
                                span_elements = social_element.find_elements(
                                    By.TAG_NAME,
                                    'span'
                                )
                                print(span_elements[1].text.lower(), span_elements[0].text)
                                self.__kols[index][span_elements[1].text.lower()].append(span_elements[0].text)

                    case 'basic info': # Get basic info
                        div_elements = contact_and_basic_info_element.find_elements(
                            By.XPATH,
                            'div/div'
                        )[1:]
                        print(f"Div elements: {len(div_elements)}")
                        for k, div_element in enumerate(div_elements):
                            span_elements = div_element.find_elements(
                                By.TAG_NAME,
                                'span'
                            )
                            print(f"Span: {len(span_elements)}")
                            if len(span_elements) == 1:
                                print(f"basicInfo{k + 1}", span_elements[0].text)
                                self.__kols[index][f"basicInfo{k + 1}"] = span_elements[0].text
                            else:
                                print(span_elements[1].text.lower(), span_elements[0].text)
                                self.__kols[index][span_elements[1].text.lower()] = span_elements[0].text
        except NoSuchElementException as e:
            logging.info(e.msg)
        except Exception as e:
            logging.info(e.msg)
        finally:
            return self.__kols[index]

    def __scrape_privacy_and_legal_info(
        self,
        driver: webdriver.Chrome,
        index: int,
    ):
        '''
            Scrape the privacy and legal info in about tab

            Params:
                driver (Chrome): current driver
                index (int): index of kol dictionary in list

            Return:
                Dictionary of kol infomation
        '''

        self.__kols["privacyAndLegalInfo"] = {}

        try:
            # Get privacy and legal info element
            privacy_and_legal_info_elements = driver.find_elements(
                By.XPATH,
                self.xpaths['privacy_and_legal_info_elements_path']
            )
            for j, privacy_and_legal_info_element in enumerate(privacy_and_legal_info_elements):
                print(j)
                # Find each part of info
                try:
                    span_tag = privacy_and_legal_info_element.find_element(
                        By.XPATH,
                        'div/div[1]/div/h2/span'
                    )
                    self.__kols["privacyAndLegalInfo"][span_tag.text.lower()] = {}
                except NoSuchElementException as e:
                    logging.info(e.msg)
                    continue

                div_elements = privacy_and_legal_info_element.find_elements(
                    By.XPATH,
                    'div/div'
                )[1:]
                print(f"Div elements: {len(div_elements)}")
                for k, div_element in enumerate(div_elements):
                    # Find each element of each part of info
                    span_elements = div_element.find_elements(
                        By.TAG_NAME,
                        'span'
                    )
                    print(f"Span: {len(span_elements)}")
                    if span_elements[1].text != "":
                        print(span_elements[1].text.lower(), span_elements[0].text)
                        self.__kols["privacyAndLegalInfo"][span_tag.text.lower()][span_elements[1].text.lower()] = span_elements[0].text
                    else:
                        print(f"contactInfo{index + 1}", span_elements[0].text)
                        self.__kols["privacyAndLegalInfo"][span_tag.text.lower()][f"{span_tag.text.lower()}{k + 1}"] = span_elements[0].text
  
        except NoSuchElementException as e:
            logging.info(e.msg)
        except Exception as e:
            logging.info(e.msg)
        finally:
            return self.__kols[index]

    def __scrape_about_tab(
        self,
        url: str,
        i: int
    ) -> Dict[str, Any]:
        '''
            Scrape the About area, just used after being logged in

            Params:
                driver (Chrome): current driver
                url (str): the url of page needing scraping
                i (int): index of kol dictionary in list

            Return:
                Dictionary of kol infomation
        '''

        # Get to the page
        driver = self.__driver_queue.get()
        driver.get(url)

        self.__kols[i]["categories"] = ""
        self.__kols[i]["email"] = ""
        self.__kols[i]["mobile"] = ""
        self.__kols[i]["address"] = ""
        self.__kols[i]["website"] = []
        self.__kols[i]["tiktok"] = []
        self.__kols[i]["instagram"] = []
        self.__kols[i]["youtube"] = []

        try:
            logging.info(f"Start scrape page {self.__kols[i]['pageName']}")

            # Navigate to about tab
            try:
                about_tab_element = driver.find_element(
                    By.XPATH,
                    self.xpaths['about_tab_element_path']
                )
                about_tab_element.click()
            except NoSuchElementException as e:
                logging.error(e.msg)
                return
            except ElementClickInterceptedException as e:
                try:
                    about_tab_element.click()
                except ElementClickInterceptedException as e:
                    logging.erroe(e.msg)
                    return

            time.sleep(5)

            # Get contact and basic info element
            self.__scrape_contact_and_basic_info(driver, i)
            
            logging.info(f"Scrape the about tab of url {driver.current_url} successfully")

        except NoSuchElementException as e:
            logging.error(e.msg)
        except Exception as e:
            pass
        finally:
            self.__driver_queue.put(driver)

            return self.__kols[i]

    def __scraper_posts(
        self,
        driver: webdriver.Chrome,
        num_posts: int,
        index: int
    ) -> None:
        '''
            Scrape posts of the kol page

            Params:
                driver (Chrome): The current  driver
                num_posts (int): Number of posts to be scrape
                index (int): Index of the kol dictionary in the list
        '''

    def __scrape_url(
        self, 
        url: str,
        i: int
    ) -> Dict[str, Any]:
        '''
            Scrape the youtube channel information from the given URLs

            Params:
                urls (str): youtube channel URL
                i (int): oredered index

            Returns:
                dict: dictionary containing channel information
        '''

        driver = self.__driver_queue.get()  # Lấy driver từ hàng đợi
        kol = {
            "id": i,
            "pageUrl": url,
            "platform": 'facebook'
        }
        url = url[:-1]
        
        try:
            # Navigate to the page
            driver.get(url)

            time.sleep(1)

            # Find the login table in center
            try:
                close_button = driver.find_element(
                    By.XPATH, 
                    self.xpaths['close_button_path']
                )
                close_button.click() # Click to close the table
            except NoSuchElementException as e:
                raise NoSuchElementException("Login de")
            except ElementClickInterceptedException as e:
                time.sleep(3)
               
                try:
                    close_button.click() # Try to click to close the table again
                except ElementClickInterceptedException:
                    raise ElementClickInterceptedException("Cannot close the table")
            
            self.__scrape_general_url(driver, kol) # Scrape general information

            logging.info(f"Scrape the page of {kol["pageName"]} with url {url} successfully")

        except NoSuchElementException: # Handle exception if we cannot access the page
            time.sleep(2) # Sleep to wait the page load
           
            exception_driver = self.__exception_driver_queue.get()
            self.__handle_login_from_main_page(exception_driver, url) # Login and take the information

            self.__scrape_general_url(exception_driver, kol) # Scrape general information

            self.__exception_driver_queue.put(exception_driver) # Pay back the exceptional driver

            logging.info(f"Scrape the page of {kol["pageName"]} with url {url} successfully")

        except Exception as e:
            logging.info(e)
        finally:
            # Add scraped time
            kol["dateCollected"] = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")

            # Add lock
            with self.__lock:
                self.__kols.append(kol)
                
            self.__driver_queue.put(driver)  # Pay back the driver to the queue

    def __handle_login_from_main_page(
        self,
        driver: webdriver.Chrome,
        url: Optional[str] = None,
    ) -> None:
        '''
            Handle login exception in the main page facebook.com if cannot access the page and try scrape again

            Params:
                driver (ChromeOptions): current driver cannot access the page
                url (str or None): the current url, if None, no url is addressed
        '''
        try:
            if not self.__is_logged_in:
                driver.get(self.FACEBOOK_URL) # Go to facebook login page

                try:
                    # Find login form
                    login_form = WebDriverWait(driver, 10).until(
                        EC.presence_of_element_located((By.XPATH, self.xpaths['login_form_path']))
                    )

                    # Find username input and fill
                    username_input = login_form.find_element(
                        By.XPATH,
                        self.xpaths['username_input_path']
                    ) 
                    for i in self.USERNAME:
                        time.sleep(0.2)
                        username_input.send_keys(i)

                    time.sleep(3)

                    # Find password input and fill
                    password_input = login_form.find_element(
                        By.XPATH,
                        self.xpaths['password_input_path']
                    )
                    for i in self.PASSWORD:
                        time.sleep(0.2)
                        password_input.send_keys(i)

                    time.sleep(3)

                    # Click login button
                    try:
                        login_button = login_form.find_element(
                            By.XPATH,
                            self.xpaths['login_button_path']
                        )
                        login_button.click()
                    except ElementClickInterceptedException as e:
                        try:
                            login_button.click()
                        except ElementClickInterceptedException as e:
                            logging.error(e.msg)
                            raise ElementClickInterceptedException("Cannot login")

                    self.__is_logged_in = True

                except NoSuchElementException as e:
                    logging.info("Element Error: " + e.msg)
                except Exception as e:
                    logging.info("Error: " + e.msg)

                time.sleep(5)

            if url:
                # Get the infomation
                driver.get(url)

        except Exception as e:
            logging.info("Cannot get the page.")

    def __handle_login_from_redirecting(
        self,
        driver: webdriver.Chrome,
        current_url: str 
    ) -> None:
        '''
            Handle login in case the driver redirects to the other page

            Params:
                driver (Chrome): the current driver
                current_url (str): the current url of the page, just use when have some exception and we want to back to the page
        '''

        try:
            # Find login form, if cannot find login form, switch to another way to login
            login_form = driver.find_element(
                By.XPATH,
                '//div[@id="loginform"]'
            )

            # Find inputs
            username_input = login_form.find_element(
                By.XPATH,
                '//input[@type="text"]'
            )
            password_input = login_form.find_element(
                By.XPATH,
                '//input[@type="password"]'
            )

            # Fill the inputs
            for i in self.USERNAME:
                time.sleep(0.2)
                username_input.send_keys(i)
            time.sleep(2)
            for i in self.PASSWORD:
                time.sleep(0.2)
                password_input.send_keys(i)

            # Find login button and click
            try:
                login_button = login_form.find_element(
                    By.XPATH,
                    '//button[@name="login"]'
                )
                login_button.click()
            except ElementClickInterceptedException as e:
                time.sleep(3)
                # Try to click again
                try:
                    login_button.click()
                except ElementClickInterceptedException as e:
                    raise ElementClickInterceptedException("Cannot login")

            if driver.current_url != current_url:
                driver.get(current_url)

        except NoSuchElementException as e:
            logging.error(e.msg)
            raise NoSuchElementException("Logging in by another way")
        except NoSuchWindowException as e: # if the window is closed
            logging.error(e.msg)
        except ElementClickInterceptedException as e:
            logging(e.msg)
        finally:
            time.sleep(3)

    def __handle_login_from_kol_page(
        self, 
        driver: webdriver.Chrome
    ) -> None:
        '''
            Handle login directly in the kol's page

            Params:
                driver (Chrome): the current driver
        '''

        try:
            # Find login form
            # login_form = driver.find_element(
            #     By.XPATH,
            #     '//div[@id="loginform"]'
            # )

            # Find inputs
            username_input = driver.find_element(
                By.XPATH,
                '/html/body/div[1]/div/div[1]/div/div[5]/div/div/div[1]/div/div[2]/div/div/div/div[2]/form/div/div[4]/div/div/label/div/input'
            )
            password_input = driver.find_element(
                By.XPATH,
                '/html/body/div[1]/div/div[1]/div/div[5]/div/div/div[1]/div/div[2]/div/div/div/div[2]/form/div/div[5]/div/div/label/div/input'
            )

            # Fill the inputs
            for i in self.USERNAME:
                time.sleep(0.2)
                username_input.send_keys(i)
            time.sleep(2)
            for i in self.PASSWORD:
                time.sleep(0.2)
                password_input.send_keys(i)

            # Find login button and click
            try:
                login_button = driver.find_element(
                    By.XPATH,
                    '/html/body/div[1]/div/div[1]/div/div[5]/div/div/div[1]/div/div[2]/div/div/div/div[2]/form/div/div[6]/div'
                )
                login_button.click()
            except ElementClickInterceptedException as e:
                time.sleep(3)
                # Try to click again
                try:
                    login_button.click()
                except ElementClickInterceptedException as e:
                    raise ElementClickInterceptedException("Cannot login")

        except NoSuchElementException as e:
            logging.error(e.msg)
            raise NoSuchElementException("Logging in by another way")
        except NoSuchWindowException as e:
            logging.error(e.msg)
        except ElementClickInterceptedException as e:
            logging(e.msg)
        finally:
            time.sleep(3)

    def start_drivers(self) -> None:
        '''
            Start the windows for the drivers
        '''

        logging.info("Starting the drivers")

        try:
            # Start all the drivers
            for _ in range(self.__num_workers):
                driver = webdriver.Chrome(service=Service(ChromeDriverManager().install()), options=self.__chrome_options)
                self.__driver_queue.put(driver)
        except Exception as e:
            logging.info("Start the driver failed")
            logging.info("Error" + e)

        logging.info("Start the drivers succesfully")

    def start_exceptional_drivers(self) -> None:
        '''
            Start the windows for exceptional drivers
        '''

        logging.info("Starting the exceptional drivers")

        # Start all the exceptional drivers
        try:
            for _ in range(self.__num_exception_workers):
                driver = webdriver.Chrome(service=Service(ChromeDriverManager().install()), options=self.__chrome_options)
                self.__exception_driver_queue.put(driver)
        except Exception as e:
            logging.info("Start the exceptional driver failed")
            logging.info("Error" + e)

        logging.info("Start the exceptional drivers succesfully")

    def scrape(
        self, 
        urls: List[str],
        is_scraping_general_info: bool = True,
        is_scraping_about_tab: bool = False,
        is_scraping_posts: bool = False
    ) -> List[Dict[str, Any]]:
        '''
            Start the scraping process

            Params:
                urls (list[str]): list of urls for scraping
                is_scraping_general_info (bool): whether scraping the general information
                is_scraping_about_tab (bool): whether scraping the about tab
                is_scraping_posts (bool): whether scraping the posts
        '''

        # Multi-threading
        with ThreadPoolExecutor(max_workers=self.__num_workers) as executor:
            # Scrape the information that not need to login
            if is_scraping_general_info:
                for i, url in enumerate(urls):
                    executor.submit(self.__scrape_url, url, i)

            # Login for each driver
            if is_scraping_about_tab or is_scraping_posts:
                for _ in range(self.__num_workers):
                    driver = self.__driver_queue.get()
                    driver.get(driver.current_url)

                    # If cannot login by this way, try another way
                    try:
                        self.__handle_login_from_redirecting(
                            driver,
                            driver.current_url
                        )
                    except NoSuchElementException:
                        self.__handle_login_from_kol_page(
                            driver
                        )

                    self.__driver_queue.put(driver)

            # Scrape the about tab
            if is_scraping_about_tab:
                for i, url in enumerate(urls):
                    executor.submit(self.__scrape_about_tab, url, i)

        return self.__kols

    def add_chrome_options(self, options: list[str]) -> None:
        '''
            Add chrome options to the chrome options list

            Params:
                options (list[str]): list of chrome options
        '''

        for option in options:
            self.__chrome_options.add_argument(option)
    
    def close(self) -> None:
        '''
            Close the drivers and free the memory 
        '''

        while not self.__driver_queue.empty():
            self.__driver_queue.get().quit()

    def reset(self) -> None:
        '''
            Reset the drivers and operations
        '''

        while not self.__driver_queue.empty():
            self.__driver_queue.get().quit()
        self.kols = []