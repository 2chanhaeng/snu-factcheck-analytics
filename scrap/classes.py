import requests
from bs4 import BeautifulSoup as bs
import yaml
import re
from typing import List, Dict, Any, Set, Tuple, Union, Optional
from tqdm import tqdm
from time import sleep


url = "http://factcheck.snu.ac.kr/v2/facts/%d"

# 발언의 정보를 저장하는 클래스를 정의합니다.
class Speaking:
    def __init__(self, num: int, predata: Optional[Dict[Any, Any]] = None):
        self.num = num
        if predata is None:
            self.responce = requests.get(url % self.num)
            if self.responce.status_code != 200:
                raise Exception(f"{self.responce.status_code} error at page {self.num}.")
            self.soup = bs(self.responce.text, 'html.parser')\
                # bs를 이용하여 구문 분석 후 soup에 저장합니다.
            self.detail = self.soup.select_one(".fcItem_detail_top") # 상세 페이지를 추출합니다.
            self.speacker = self.detail.select_one(".name").text.strip() # 발언자를 추출합니다.
            self.title = self.detail.select_one(".fcItem_detail_li_p > p:nth-child(1) > a").text.strip() # 제목을 추출합니다.
            self.source_element = self.detail.select_one(".source") # 출처가 담긴 html 요소를 추출합니다.
            self.source = {self.source_element.text.strip(): ""} \
                if self.source_element.select_one("a") == None\
                else {self.source_element.select_one("a").text.strip(): self.source_element.select_one("a")['href']} # 출처를 추출합니다.
            self.cartegories = {li.text for li in self.detail.select(".fcItem_detail_bottom li")} # 카테고리를 추출합니다.
            self.explain = self.soup.select_one(".exp").text.strip() # 설명을 추출합니다.
            self.factchecks = self.get_fc(self.soup)
        else:
            self.speacker = predata['speacker']
            self.title = predata['title']
            self.source = predata['source']
            self.cartegories = predata['cartegories']
            self.explain = predata['explain']
            self.factchecks = predata['factchecks']
    
    def as_dict(self): # 데이터를 딕셔너리 형태로 반환합니다.
        return {
            'speacker': self.speacker,
            'title': self.title,
            'source': self.source,
            'cartegories': self.cartegories,
            'explain': self.explain,
            'factchecks': self.factchecks
        }
    
    def as_yaml(self): # 데이터를 yaml 형태로 반환합니다.
        return yaml.dump(self.as_dict(), allow_unicode=True)

    def save_as_yaml(self, path:str):
        with open(path, 'w') as f:
            f.write(self.as_yaml())

    # SNU 팩트체크 사이트는 다음과 같이 팩트 체크 별 아이디와 점수를 보냅니다.
    # <ul> <li class="fcItem_vf_li">...</li>
    # <script charset="utf-8" type="text/javascript">
    # $(function () { showScore(아이디, 점수)}); </script> ... </ul>
    # 따라서 아이디와 점수를 추출하는 정규표현식을 사용합니다.

    
    # 아이디와 점수를 추출하는 함수를 정의합니다.

    def get_fc_id_score(self, soup:bs) -> List[Tuple[int, int]]:
        id_score: List[Tuple[int,int]] = [] # 아이디와 점수를 저장할 리스트
        id_score_re = re.compile(r'(?<=showScore\()\d+, \d+')
        for fc_item_script in soup.select(".fcItem_vf > ul > script"): # 팩트 체크 아이템의 스크립트를 찾습니다.
            id_score_str: str = id_score_re.search(fc_item_script.text).group() # 정규 표현식으로 아이디와 점수값을 담은 문자열을 추출합니다.
            id_score_int: Tuple = tuple(map(int, id_score_str.split(', '))) # 문자열을 정수로 변환합니다.
            id_score.append(id_score_int)
        return id_score



    # 작성 시간과 내용을 추출하는 함수를 정의합니다.

    def get_fc_time_contents(self, soup:bs) -> List[Tuple[str, str, str]]:
        time_contents: List[str] = [] # 시간과 내용을 저장할 리스트
        for fc_item in soup.select(".fcItem_vf > ul > li"): # 팩트 체크 아이템을 찾습니다.
            date = fc_item.select_one(".reg_date > p i:nth-child(1)").text # 작성 날짜를 추출합니다.
            time = fc_item.select_one(".reg_date > p i:nth-child(2)").text # 작성 시간을 추출합니다.
            raw_content = fc_item.select_one(".vf_exp_wrap").text # 팩트 체크 내용을 추출합니다.
            content = re.sub(r'\s{2,}', " ", raw_content.strip()) # 공백을 제거합니다.
            time_contents.append((date, time, content))
        return time_contents

    # 위의 함수들의 반환을 합쳐 최종적으로 아이디를 키로 갖고 나머지 내용을 값으로 갖는 딕셔너리를 반환하는 함수를 정의합니다.

    def get_fc(self, soup:bs) -> Dict[int, Dict[Any, Any]]:
        id_score = self.get_fc_id_score(soup) # 아이디와 점수를 추출합니다.
        time_contents = self.get_fc_time_contents(soup) # 작성 시간과 내용을 추출합니다.
        zipped = zip(id_score, time_contents) # 두 리스트를 합쳐 쌍을 생성합니다.
        return {id: {'score': score, 'date': date, 'time': time, 'content': content} for (id, score), (date, time, content) in zipped}


# Speaking 객체를 스크래핑하는 함수를 정의합니다.
def scrap_speaking(how_many:int = 4000, stop_when_errors_continued: int = 20) -> List[Speaking]:
    speakings: List[Speaking] = []
    errors: Set[int] = set()
    continued_errors: int = 0
    
    for i in tqdm(range(1,how_many + 1)):
        try:
            speakings.append(Speaking(i))
            continued_errors = 0
        except:
            errors.add(i)
            continued_errors += 1
            if continued_errors > stop_when_errors_continued:
                print(f"{i}번째 페이지까지 스크래핑하는데 에러가 연속으로 {continued_errors}번 발생했습니다. 스크래핑을 중단합니다.")
                break
        if i % 10 == 0:
            sleep(1)
    print(f"업데이트된 데이터의 수는 {len(speakings)}/{how_many}개 입니다.")
    return speakings


# 스크래핑한 Speaking 객체들의 데이터를 저장하는 함수를 정의합니다.
def save_speaking(data: Any, file_name: str = 'speakings.yaml'):
    if type(data) is not str:
        yaml.dump(data, open(file_name, 'w', encoding="utf-8"), default_flow_style=False, allow_unicode=True)
    else:
        with open(file_name, 'w', encoding="utf-8") as f:
            f.write(data)


# .yaml으로 저장했던 Speaking 객체들의 정보를 딕셔너리로 불러오는 함수를 정의합니다.
def load_speakings_as_dict(file_name: str = 'speakings.yaml') -> Dict[Any, Any]:
    speaks_dict = yaml.load(open(file_name, 'r', encoding="utf-8"), Loader=yaml.FullLoader)
    if type(speaks_dict) is dict:
        return speaks_dict
    else:
        raise TypeError(f"{file_name} 이 딕셔너리로 저장되지 않았습니다. 현재 저장된 타입은 {type(speaks_dict)} 입니다.")


# .yaml으로 저장했던 Speaking 객체들을 불러오는 함수를 정의합니다.
def load_speakings(file_name: str = 'speakings.yaml') -> List[Speaking]:
    speaks_dict = load_speakings_as_dict(file_name)
    speakings = [Speaking(id, contents) for id, contents in speaks_dict.items()]
    return speakings


speakings: List[Speaking] = load_speakings()
speaks_dict: Dict[Any, Any] = load_speakings_as_dict()

# 저장되어 있는 Speaking 데이터 베이스를 업데이트하는 함수를 정의합니다.
def update_speakings(file_name: str = 'speakings.yaml', how_many: int = 100, stop_when_errors_continued: int = 10):
    from os.path import exists
    # file_name 파일이 존재하면 파일을 로드하여 가장 큰 key 부터, 없으면 0부터 시작합니다.
    if exists(file_name):
        speaks_dict = load_speakings_as_dict(file_name)
        last_id =  max(speaks_dict.keys())
    else:
        speaks_dict = {}
        last_id = 0

    speakings: Dict[int, Dict[Any, Any]] = {}
    errors: Set[int] = set()
    continued_errors = 0
    
    # last_id + 1 부터 최대 how_many 개의 
    for i in tqdm(range(last_id + 1, last_id + how_many)):
        try:
            speakings[i] = Speaking(i).as_dict()
            continued_errors = 0
        except:
            # speakings.append(None)
            errors.add(i)
            continued_errors += 1
            if continued_errors >= stop_when_errors_continued:
                print(f"{i}번째 페이지까지 스크래핑하는데 에러가 연속으로 {continued_errors}번 발생했습니다. 스크래핑을 중단합니다.")
                break
        if i % 10 == 0:
            sleep(1)
    if len(speakings) < 1:
        print("업데이트된 데이터가 없습니다.")
        return
    print(f"업데이트된 데이터의 수는 {len(speakings)}/{how_many}개 입니다.")
    speaks_dict.update(speakings)
    save_speaking(speakings, file_name)