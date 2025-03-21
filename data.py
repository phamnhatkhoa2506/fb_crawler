import json
import os

from typing import List, Dict, Any

def read_urls(filepath: str) -> list[str]:
    '''
        Read urls from a file
        
        Params:
            filepath (str): path to the file containing the urls

        Returns:
            List of urls
    '''
    
    try:
        with open(filepath, 'r') as f:
            urls = f.readlines()
    except FileNotFoundError:
        print(f"File {filepath} not found")

    return urls


def save_data(data: List[Dict[str, Any]], filepath: str) -> None:
    '''
        Save the data as json

        Params:
            data (list[dict]): list of data in dictionary format
            filepath (str): the path of saved file
    '''

    dirname = os.path.dirname(os.path.abspath(filepath)) # File the folder of file
    os.makedirs(dirname, exist_ok=True)

    with open(filepath, 'w', encoding='utf-8') as f:
        json.dump(data, f, indent=4, ensure_ascii=False)