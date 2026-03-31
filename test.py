import requests
import pandas as pd
import time
import random
import re
from typing import List, Dict, Set
from tqdm import tqdm

# ==================== 配置区（对应你的16国列表） ====================
COUNTRY_CONFIG = {
    "American": {"qid": "Q30", "type": "country"},  # USA
    "British": {"qid": "Q145", "type": "country"},  # UK
    "Chinese": {"qid": "Q148", "type": "country"},  # PRC
    "Dutch": {"qid": "Q55", "type": "country"},  # Netherlands
    "French": {"qid": "Q142", "type": "country"},  # France
    "German": {"qid": "Q183", "type": "country"},  # Germany
    "Indian": {"qid": "Q668", "type": "country"},  # India
    "Italian": {"qid": "Q38", "type": "country"},  # Italy
    "Japanese": {"qid": "Q17", "type": "country"},  # Japan
    "Korean": {"qid": "Q884", "type": "country"},  # South Korea
    "Polish": {"qid": "Q36", "type": "country"},  # Poland
    "Portuguese": {"qid": "Q45", "type": "country"},  # Portugal
    "Russian": {"qid": "Q159", "type": "country"},  # Russia
    "Spanish": {"qid": "Q29", "type": "country"},  # Spain
    "Vietnamese": {"qid": "Q881", "type": "country"},  # Vietnam
    "Arabic": {"qid": "Q7172", "type": "union"},  # Arab League（方案C）
}

# ==================== 常量配置 ====================
TARGET_PER_COUNTRY = 2000  # 每国需求2000条
TRAIN_RATIO = 0.7  # 70%训练集
BATCH_SIZE = 500  # 每次SPARQL查询条数（Wikidata限制）
MAX_RETRIES = 5  # 最大重试次数
RETRY_DELAY_BASE = 2  # 指数退避基数（秒）
SPARQL_ENDPOINT = "https://query.wikidata.org/sparql"

# 7层过滤规则常量
STOP_WORDS = [
    r"(?i)list of",
    r"(?i)history of",
    r"(?i)battle of",
    r"(?i)war of",
    r"(?i)university",
    r"(?i)college",
    r"(?i)company",
    r"(?i)inc\.?",
    r"(?i)corp\.?",
    r"(?i)foundation",
    r"(?i)association",
    r"(?i)institute",
    r"(?i)organization",
    r"(?i)party",
    r"(?i)movement",
    r"(?i)dynasty",
    r"(?i)empire",
    r"(?i)kingdom",
    r"(?i)republic of",
    r"(?i)disambiguation",
]

# 字母表与格式正则
VALID_NAME_PATTERN = re.compile(
    r"^[A-Za-z\s\-\'\.]+$"
)  # L2：仅允许英文字母、空格、连字符、撇号、句点
DISAMBIG_PATTERN = re.compile(r"\(.*disambiguation.*\)", re.I)  # L4：消歧页标记
ALL_UPPER = re.compile(r"^[A-Z]+$")  # L5：全大写检测
ALL_LOWER = re.compile(r"^[a-z]+$")  # L5：全小写检测
VOWEL_PATTERN = re.compile(r"[aeiouAEIOU]")  # L6：元音检测


class WikidataNameScraper:
    """
    Wikidata人名抓取器
    实现功能：强制性扒取（未到2000条不停）、7层数据清洗、分层抽样
    """

    def __init__(self):
        self.session = requests.Session()
        self.session.headers.update(
            {
                "User-Agent": "NameNationalityScraper/1.0 (Academic Research)",
                "Accept": "application/sparql-results+json",
            }
        )

    def _make_sparql_query(self, country_name: str, offset: int) -> List[Dict]:
        """
        【需求实现：方案C - Arabic使用阿拉伯联盟聚合查询】
        构建SPARQL查询，对Arabic使用wdt:P17*（行政领土实体）捕获联盟内所有成员国
        """
        config = COUNTRY_CONFIG[country_name]
        qid = config["qid"]

        if config["type"] == "union":
            # 方案C：Arabic - 捕获阿拉伯联盟(Q7172)内所有国家的国籍
            # 使用P17*路径查询：人物国籍所在国家属于阿拉伯联盟
            query = f"""
            SELECT DISTINCT ?person ?name
            WHERE {{
              ?person wdt:P31 wd:Q5;
                      wdt:P27 ?country;
                      rdfs:label ?name.
              ?country wdt:P17 wd:Q7172.  # 国家属于阿拉伯联盟
              FILTER(LANG(?name) = "en")
              FILTER(STRLEN(?name) >= 2)
            }}
            LIMIT {BATCH_SIZE}
            OFFSET {offset}
            """
        else:
            # 标准国家查询：直接匹配P27（国籍）
            query = f"""
            SELECT DISTINCT ?person ?name
            WHERE {{
              ?person wdt:P31 wd:Q5;           # 【L1】强制为人类(Q5)
                      wdt:P27 wd:{qid};        # 指定国籍
                      rdfs:label ?name.
              FILTER(LANG(?name) = "en")        # 仅英文标签
              FILTER(STRLEN(?name) >= 2)        # 基础长度过滤
            }}
            LIMIT {BATCH_SIZE}
            OFFSET {offset}
            """

        for attempt in range(MAX_RETRIES):
            try:
                response = self.session.get(
                    SPARQL_ENDPOINT,
                    params={"query": query, "format": "json"},
                    timeout=30,
                )

                if response.status_code == 429:
                    # 【需求实现：API限流处理】指数退避重试
                    delay = RETRY_DELAY_BASE * (2**attempt) + random.uniform(0, 1)
                    print(
                        f"  ⚠️  429限流，等待{delay:.1f}秒后重试({attempt + 1}/{MAX_RETRIES})..."
                    )
                    time.sleep(delay)
                    continue

                response.raise_for_status()
                data = response.json()
                results = data.get("results", {}).get("bindings", [])
                return [
                    {"person": r["person"]["value"], "name": r["name"]["value"]}
                    for r in results
                ]

            except requests.exceptions.RequestException as e:
                delay = RETRY_DELAY_BASE * (2**attempt)
                print(f"  ⚠️  网络错误({e})，{delay}秒后重试...")
                time.sleep(delay)
                if attempt == MAX_RETRIES - 1:
                    print(f"  ❌  达到最大重试次数，返回空结果")
                    return []

        return []

    def _apply_filters(self, raw_names: List[str], country: str) -> List[str]:
        """
        【需求实现：7层数据清洗】逐层过滤垃圾数据与错误姓名
        返回清洗后的名字列表
        """
        cleaned = []

        for name in raw_names:
            name = name.strip()

            # L1：实体类型已在SPARQL中通过wdt:P31 wd:Q5保证
            # 此处进行额外的长度截断（防止超长脏数据）
            if len(name) > 50:
                continue

            # L2：字母表净化 - 仅保留标准ASCII英文字母及常见分隔符
            if not VALID_NAME_PATTERN.match(name):
                continue

            # L3：停用词黑名单 - 排除机构、列表、消歧页等
            if any(re.search(pattern, name) for pattern in STOP_WORDS):
                continue

            # L4：消歧页过滤 - 严格排除含(disambiguation)的条目
            if DISAMBIG_PATTERN.search(name):
                continue

            # L5：长度与格式验证
            if len(name) < 2:  # 太短
                continue
            if ALL_UPPER.match(name) or ALL_LOWER.match(
                name
            ):  # 全大写或全小写（可能是缩写或脏数据）
                continue

            # L6：词元验证 - 必须包含至少一个元音（排除"Krzysztof"这类有效但难处理的波兰名？不，波兰名也有元音）
            # 实际功能：排除纯辅音垃圾数据如"XYZ"、"BDF"
            if not VOWEL_PATTERN.search(name):
                continue

            # 通过所有过滤层
            cleaned.append(name)

        return cleaned

    def scrape_country(self, country_name: str) -> List[str]:
        """
        【需求实现：强制性扒取】
        逻辑：循环查询直到 collected >= 2000 或数据源耗尽
        包含去重机制（同一国家内同名只保留一条）
        """
        print(f"\n🇺🇳 开始抓取: {country_name}")
        collected = set()  # 使用集合去重（L7）
        offset = 0
        empty_streak = 0  # 连续空结果计数器，用于检测数据源耗尽

        with tqdm(total=TARGET_PER_COUNTRY, desc=f"{country_name}") as pbar:
            while len(collected) < TARGET_PER_COUNTRY:
                batch = self._make_sparql_query(country_name, offset)

                if not batch:
                    empty_streak += 1
                    if empty_streak >= 3:  # 连续3次空结果，认为数据源耗尽
                        print(
                            f"  ⚠️  {country_name} 数据源已耗尽，当前收集: {len(collected)}/{TARGET_PER_COUNTRY}"
                        )
                        break
                    offset += BATCH_SIZE  # 继续尝试下一页（可能中间有间隙）
                    continue
                else:
                    empty_streak = 0  # 重置空结果计数

                # 提取名字并清洗
                raw_names = [item["name"] for item in batch]
                filtered = self._apply_filters(raw_names, country_name)

                # L7：去重（集合自动处理）
                before_dedup = len(collected)
                for name in filtered:
                    collected.add(name)

                new_added = len(collected) - before_dedup
                pbar.update(new_added)

                # 检查是否卡死（无新数据增加但循环继续）
                if (
                    len(batch) > 0
                    and new_added == 0
                    and len(collected) < TARGET_PER_COUNTRY
                ):
                    # 可能当前批次全是重复或脏数据，增加offset跳过
                    offset += BATCH_SIZE
                else:
                    offset += len(batch)  # 正常推进

                # 礼貌延迟，避免触发Wikidata限流
                time.sleep(0.5)

                # 如果已经遍历了很大范围仍未满，可能该语言数据确实不足
                if offset > 100000 and len(collected) < TARGET_PER_COUNTRY:
                    print(
                        f"  ⚠️  已遍历100k条候选，仅收集{len(collected)}条有效，可能数据稀缺"
                    )
                    break

        result_list = list(collected)
        if len(result_list) > TARGET_PER_COUNTRY:
            result_list = result_list[:TARGET_PER_COUNTRY]  # 截断至正好2000

        print(f"  ✅ {country_name}: 成功收集 {len(result_list)} 条")
        return result_list

    def stratified_split(
        self, all_data: Dict[str, List[str]]
    ) -> (pd.DataFrame, pd.DataFrame):
        """
        【需求实现：分层70/30分割】
        确保每个国家严格按70%训练、30%测试分割，保持类别平衡
        """
        train_records = []
        test_records = []

        for country, names in all_data.items():
            n_total = len(names)
            n_train = int(n_total * TRAIN_RATIO)

            # 随机打乱（固定种子保证可复现）
            random.seed(42)
            shuffled = names.copy()
            random.shuffle(shuffled)

            train_names = shuffled[:n_train]
            test_names = shuffled[n_train:]

            # 构造DataFrame记录
            for name in train_names:
                train_records.append({"name": name, "country": country})
            for name in test_names:
                test_records.append({"name": name, "country": country})

            print(f"  {country}: 训练集 {len(train_names)} | 测试集 {len(test_names)}")

        train_df = pd.DataFrame(train_records)
        test_df = pd.DataFrame(test_records)

        return train_df, test_df


def main():
    """
    主执行流程
    """
    scraper = WikidataNameScraper()
    all_country_data = {}

    # 【需求实现：16国×2000条强制性扒取】
    print("=" * 60)
    print("阶段1: 强制性数据扒取 (每国2000条，未满继续)")
    print("=" * 60)

    for country in COUNTRY_CONFIG.keys():
        names = scraper.scrape_country(country)
        all_country_data[country] = names
        # 每国抓取后保存中间结果（防崩溃丢失）
        pd.DataFrame({"name": names, "country": country}).to_csv(
            f"temp_{country}.csv", index=False, encoding="utf-8"
        )

    # 【需求实现：分层70/30分割】
    print("\n" + "=" * 60)
    print("阶段2: 分层抽样 (训练集70%，测试集30%)")
    print("=" * 60)

    train_df, test_df = scraper.stratified_split(all_country_data)

    # 验证分布
    print("\n训练集分布:")
    print(train_df["country"].value_counts())
    print("\n测试集分布:")
    print(test_df["country"].value_counts())

    # 保存最终数据集（与你的Python代码格式对齐）
    train_df.to_csv("train_wiki_cleaned.csv", index=False, encoding="utf-8")
    test_df.to_csv("test_wiki_cleaned.csv", index=False, encoding="utf-8")

    print("\n" + "=" * 60)
    print("完成!")
    print(f"训练集: {len(train_df)} 条 (70%) -> train_wiki_cleaned.csv")
    print(f"测试集: {len(test_df)} 条 (30%) -> test_wiki_cleaned.csv")
    print("=" * 60)

    # 统计报告
    total_target = len(COUNTRY_CONFIG) * TARGET_PER_COUNTRY
    total_actual = sum(len(v) for v in all_country_data.values())
    print(
        f"\n采集完成度: {total_actual}/{total_target} ({100 * total_actual / total_target:.1f}%)"
    )


if __name__ == "__main__":
    main()
