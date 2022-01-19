from email.policy import default
import requests
from bs4 import BeautifulSoup as bs
import yaml
import re
from typing import List, Dict, Any, Set, Tuple, Union, Optional
from tqdm import tqdm
from time import sleep

__all__ = ['Speaking', 'speakings', 'speaks_dict']

url = "http://factcheck.snu.ac.kr/v2/facts/%d"
saving_path = "scrap/speakings.yaml"
try:
    default_yaml_loader = yaml.CLoader
    default_yaml_dumper = yaml.CDumper
except AttributeError:
    default_yaml_loader = yaml.FullLoader
    default_yaml_dumper = yaml.FullDumper


# 발언의 정보를 저장하는 클래스를 정의합니다.
class Speaking:
    def __init__(self, num: int, predata: Optional[Dict[Any, Any]] = None):
        self.num = num
        if predata is None: # id를 이용해 정보를 요청합니다.
            self.responce = requests.get(url % self.num)
            if self.responce.status_code != 200:
                raise Exception(f"{self.responce.status_code} error at page {self.num}.")
            self.soup = bs(self.responce.text, 'html.parser')\
                # bs를 이용하여 구문 분석 후 soup에 저장합니다.
            self.detail = self.soup.select_one(".fcItem_detail_top") # 상세 페이지를 추출합니다.
            self.speaker = self.detail.select_one(".name").text.strip() # 발언자를 추출합니다.
            self.title = self.detail.select_one(".fcItem_detail_li_p > p:nth-child(1) > a").text.strip() # 제목을 추출합니다.
            self.source_element = self.detail.select_one(".source") # 출처가 담긴 html 요소를 추출합니다.
            self.source = {self.source_element.text.strip(): ""} \
                if self.source_element.select_one("a") == None\
                else {self.source_element.select_one("a").text.strip(): self.source_element.select_one("a")['href']} # 출처를 추출합니다.
            self.categories = {li.text for li in self.detail.select(".fcItem_detail_bottom li")} # 카테고리를 추출합니다.
            self.explain = self.soup.select_one(".exp").text.strip() # 설명을 추출합니다.
            self.factchecks = self.get_fc(self.soup)
        else: # 기존 데이터를 로드해서 객체를 다시 생성합니다.
            self.speaker = predata['speaker']
            self.title = predata['title']
            self.source = predata['source']
            self.categories = predata['categories']
            self.explain = predata['explain']
            self.factchecks = predata['factchecks']
    
    def __dict__(self):
        return {
            'speaker': self.speaker,
            'title': self.title,
            'source': self.source,
            'categories': self.categories,
            'explain': self.explain,
            'factchecks': self.factchecks
        }

    def check_key(self, key:str) -> None:
        if type(key) is not str:
            raise TypeError(f"{key} 는 문자열이 아닙니다.")
        if key not in dict(self).keys():
            raise KeyError(f"{key} 는 존재하지 않는 키입니다.")

    def __getitem__(self, key:str) -> Any:
        self.check_key(key)
        return self.key
    
    def __setitem__(self, key:str, value:Any):
        self.check_key(key)
        self.key = value
    
    def __delitem__(self, key:str):
        self.check_key(key)
        self.key = None

    def as_dict(self): # 데이터를 딕셔너리 형태로 반환합니다.
        return {
            'speaker': self.speaker,
            'title': self.title,
            'source': self.source,
            'categories': self.categories,
            'explain': self.explain,
            'factchecks': self.factchecks
        }
    
    def as_yaml(self): # 데이터를 yaml 형태로 반환합니다.
        return yaml.dump(self.as_dict(), allow_unicode=True, Dumper=default_yaml_dumper)


    def save_as_yaml(self, path:str): # 데이터를 yaml 형태로 저장합니다.
        with open(path, 'w') as f:
            f.write(self.as_yaml())

    # SNU 팩트체크 사이트는 다음과 같이 팩트 체크 별 아이디와 점수를 보냅니다.
    # <ul> <li class="fcItem_vf_li">...</li>
    # <script charset="utf-8" type="text/javascript">
    # $(function () { showScore(아이디, 점수)}); </script> ... </ul>
    # 따라서 아이디와 점수를 추출하는 정규표현식을 사용합니다.
    id_score_re = re.compile(r'(?<=showScore\()\d+, \d+')

    # 아이디와 점수를 추출하는 함수를 정의합니다.
    def get_fc_id_score(self, soup:bs) -> List[Tuple[int, int]]:
        id_score: List[Tuple[int,int]] = [] # 아이디와 점수를 저장할 리스트
        for fc_item_script in soup.select(".fcItem_vf > ul > script"): # 팩트 체크 아이템의 스크립트를 찾습니다.
            id_score_str: str = Speaking.id_score_re.search(fc_item_script.text).group() # 정규 표현식으로 아이디와 점수값을 담은 문자열을 추출합니다.
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
    @staticmethod
    def scrap_speaking(how_many:int = 4000, stop_when_errors_continued: int = 20) -> List['Speaking']:
        speakings: List[Speaking] = []
        errors: Set[int] = set()
        continued_errors: int = 0 # 연속된 에러가 발생한 횟수를 저장합니다.
        
        for i in tqdm(range(1,how_many + 1)):
            try:
                speakings.append(Speaking(i))
                continued_errors = 0 # 에러가 없으면 에러 횟수를 0으로 초기화합니다.
            except:

                # 에러가 발생하면 에러를 저장하고 연속된 에러 횟수를 증가시킵니다. 
                errors.add(i)
                continued_errors += 1

                # 연속된 에러가 정해진 횟수를 넘어가면 종료합니다.
                if continued_errors > stop_when_errors_continued: 
                    print(f"{i}번째 페이지까지 스크래핑하는데 에러가 연속으로 {continued_errors}번 발생했습니다. 스크래핑을 중단합니다.")
                    break
        print(f"업데이트된 데이터의 수는 {len(speakings)}/{how_many}개 입니다.")
        return speakings


    # 스크래핑한 Speaking 객체들의 데이터를 저장하는 함수를 정의합니다.
    @staticmethod

    def save_speakings(data: Any, file_name: str = saving_path):
        if type(data) is not str: # 데이터가 문자열이 아니면 yaml 형식으로 변환합니다.
            yaml.dump(data, open(file_name, 'w', encoding="utf-8"), default_flow_style=False, allow_unicode=True, Dumper=default_yaml_dumper)
        else:
            with open(file_name, 'w', encoding="utf-8") as f:
                f.write(data)


    # .yaml으로 저장했던 Speaking 객체들의 정보를 딕셔너리로 불러오는 함수를 정의합니다.
    @staticmethod
    def load_speakings_as_dict(file_name: str = saving_path) -> Dict[Any, Any]:
        speaks_dict = yaml.load(open(file_name, 'r', encoding="utf-8"), Loader=default_yaml_loader)
        if type(speaks_dict) is dict: # 불러온 데이터가 딕셔너리면 그대로 반환합니다.
            return speaks_dict
        else: # 불러온 데이터가 딕셔너리가 아니면 에러를 발생시킵니다.
            raise TypeError(f"{file_name} 이 딕셔너리로 저장되지 않았습니다. 현재 저장된 타입은 {type(speaks_dict)} 입니다.")


    # .yaml으로 저장했던 Speaking 객체들을 불러오는 함수를 정의합니다.
    @staticmethod
    def load_speakings(file_name: str = saving_path) -> List['Speaking']:
        speaks_dict = Speaking.load_speakings_as_dict(file_name)
        speakings = [Speaking(id, contents) for id, contents in speaks_dict.items()]
        return speakings


    # 저장되어 있는 Speaking 데이터 베이스를 업데이트하는 함수를 정의합니다.
    @staticmethod
    def update_speakings(file_name: str = saving_path, how_many: int = 100, stop_when_errors_continued: int = 10):
        # file_name 파일이 존재하면 파일을 로드하여 가장 큰 key 부터, 없으면 0부터 시작합니다.
        from os.path import exists
        if exists(file_name):
            speaks_dict = Speaking.load_speakings_as_dict(file_name)
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
        Speaking.save_speaking(speaks_dict, file_name)

speakings: List[Speaking] = Speaking.load_speakings()
speaks_dict: Dict[Any, Any] = Speaking.load_speakings_as_dict()