from dataclasses import dataclass
from datetime import datetime
from string import Template

# 数据库配置
DB_USER = "daal"
DB_PASSWORD = "daal"
DB_HOST = "localhost"
DB_PORT = "5433"
DB_NAME = "test_db"

DATABASE_URL = f"postgresql://{DB_USER}:{DB_PASSWORD}@{DB_HOST}:{DB_PORT}/{DB_NAME}"

# 会议信息 NeurIPS 2024
START_DATE = datetime(2024, 12, 10)
END_DATE = datetime(2024, 12, 15)
LOCATION = "Vancouver, Canada"
WEBSITE = "https://neurips.cc/virtual/2024/index.html"
CATEGORY = "machine learning, neuroscience, statistics, optimization, computer vision, natural language processing, life sciences, natural sciences, social sciences"
DESCRIPTION = "The Conference and Workshop on Neural Information Processing Systems is a machine learning and computational neuroscience conference held every December. Along with ICLR and ICML, it is one of the three primary conferences of high impact in machine learning and artificial intelligence research."


@dataclass
class MilvusConfig:
    host: str = "localhost"
    port: int = 19530
    collection_name: str = "paper_collection"
    dimension: int = 768  # Embedding dimension
    index_type: str = "IVF_FLAT"
    metric_type: str = "L2"


class PDFAnalyzerConfig:
    # 定义各个章节的标题, 用于提取章节内容.可以持续刷新
    SECTION_TITLES = {
        "abstract": {"abstract"},
        "introduction": {"introduction", "background", "preliminaries", "preliminary"},
        "keywords": {"keywords", "key words", "index terms", "indexing terms"},
        "related_work": {
            "related work",
            "prior work",
            "literature review",
            "related studies",
        },
        "methodology": {
            "methodology",
            "methods",
            "method",
            "approach",
            "proposed method",
            "model",
            "architecture",
            "framework",
            "algorithm",
            "system design",
        },
        "experiment": {
            "experiment",
            "experiments",
            "experimental setup",
            "experiment setup",
            "setup",
            "implementation details",
            "evaluation",
            "evaluation setup",
        },
        "ablation": {"ablation", "ablation study"},
        "results": {
            "results",
            "performance",
            "findings",
            "observations",
            "empirical results",
        },
        "discussion": {"discussion", "analysis", "interpretation"},
        "summary": {"summary"},
        "conclusion": {"conclusion", "final remarks", "closing remarks"},
        "limitations": {"limitations"},
        "acknowledgments": {
            "acknowledgments",
            "acknowledgements",
            "funding",
            "author contributions",
        },
        "references": {"references", "bibliography", "cited works"},
        "appendix": {
            "appendix",
            "supplementary material",
            "supplementary",
            "additional materials",
        },
    }
    # 论文拆分参数
    MAX_LINE_PER_CHUNK = 50  # 每个 chunk 最大行数
    OVERLAP_LINES = 5  # 上下文重叠行数
    REFERENCE_CHUNK_LINE_SIZE = 24  # 参考文献一个chunk的行数量,假设3行算一个reference
    REFERENCE_MAX_CHUNK_SIZE = 10  # 一篇文章的reference 假设有个最长，避免某些文章在reference 之后放了很长的不相干文字。以上两个数相乘
    REFERENCE_OVERLAP_LINES = 3  # 参考文献块重叠行数

    # 定义提示词模版
    AUTHOR_AFFILIATION_PROMPT_TEMPLATE = Template(
        """
        ### Instruction:

        Your task is to generate an updated JSON array to get more information about the authors based on the paper text following these steps:
        For each author do:

        Step 1: Identify the Author in the Text
        - Locate the author’s name in the paper text, paying attention to superscript numbers or symbols next to the name.

        Step 2: Identify ONLY the Highest-Level Institution Name in the Text
        - Look for superscript numbers/markers (¹, ², ³, *, +, #) next to the author's name in the text.
        - Identify the institution names following these markers. Only extract the highest level of affiliation, such as universities, research institutes, or companies (e.g., Harvard University, MIT, Google).
        - **Ignore** specific departments, labs, or teams; only consider broad institutions (e.g., "Department of Physics" should be ignored in favor of "Harvard University").
        
        Step 3: Identify the Email in the Text
        - Look for email addresses associated with the author. These may be explicitly stated in the paper or in contact information sections.
        - Check for email addresses marked with symbols such as *, †, or other similar markers.
        - Ensure the email address is correctly identified, especially if associated with the corresponding author.

        Step 4: Guess Nationality Based on Name or Email
        - If no clear inference can be made, leave the field blank or set a default if needed.

        Step 5: Prepare the Final JSON Output
        - For each identified author, create a JSON object with the following fields:
        - name: Retain the existing author_name
        - author_id: Retain the existing author_id
        - affiliation: Extracted list of highest-level affiliations
        - email: Extracted email address
        - nationality: Inferred nationality based on name or email

        ### Output Format:

        - Only output the updated JSON array (no lead-in text, no explanations, no code snippets, no intermediate reasoning).
        - Ensure the JSON output is valid and parsable.
        - Return the order of author the same as the author's order in the given json input.

        ---

        ### Input:
        Paper Text:
        $context

        Authors:
        $author_json

        ---

        ### Output:
        Return **only a raw JSON object**. **No explanations or extra text**.

        Example output:
        ```json
        [
            {
                "name": "Ryan Greenblatt",
                "author_id": "~Ryan_Greenblatt1",
                "affiliation": ["Redwood Research"],
                "email": "ryan@rdwrs.com",
                "nationality": "United States"
            },
            {
                "name": "Fabien Roger",
                "author_id": "~Fabien_Roger1",
                "affiliation": ["Redwood Research"],
                "email": "fabien.d.roger@gmail.com",
                "nationality": "France"
            }
        ]                                                                   
        """
    )

    REFERENCES_PROMPT_TEMPLATE = Template(
        """
        You will be given several citation fragments from academic papers.  
        Your task is to extract key citation information **only if** the citation fragment appears to be a valid reference.  
        If the fragment is **not** a valid reference (e.g., a broken or incomplete reference, or unrelated information), **return an empty list**.

        Each valid citation should return a JSON object with the following fields:

        - "title": (string, required) The title of the cited paper.  
        - "author": (string) Authors separated by commas. Use "unknown" if not available.  
        - "year": (integer) Year of publication. Use null if unknown.  
        - "journal": (string) Journal or publication name. Use "unknown" if not available.  
        - "web_url": (string) URL to the original paper or web source. Use "unknown" if not available.  

        ### Input:
        $reference_chunk_text

        ### Important Notes:
        - **If the input does not appear to be a valid reference**, skip it and return an empty array.  
        - Extract as much accurate information as possible from valid references.  
        - Return **only a raw JSON array** of citation objects (or an empty array if invalid).  
        - **Do not include any explanations, comments, or extra text.**  
        - Ensure the JSON is well-formed and parsable.  
        - For unknown or missing information, use `"unknown"` or `null` where appropriate.  

        ### Example Output:
        ```json
        [
        {
            "title": "Program synthesis with large language models",
            "author": "Austin, J., Odena, A., Nye, M., Bosma, M., Michalewski, H., et al.",
            "year": 2021,
            "journal": "arXiv preprint arXiv:2108.07732",
            "web_url": "https://arxiv.org/abs/2108.07732"
        },
        {
            "title": "Cooperative Hardware-Prompt Learning for Snapshot Compressive Imaging",
            "author": "unknown",
            "year": null,
            "journal": "unknown",
            "web_url": "unknown"
        }
        ]
        """
    )
    KEYWORDS_PROMPT_TEMPLATE = Template(
        """
        You are an expert academic assistant. Your task is to extract the most important keywords that represent the core ideas of the given research paper.

        You will be provided with:
        - The **abstract** of the paper (may be empty if not available).
        - The **conclusion** of the paper (may be empty if not available).
        - An optional **TL;DR summary** (if available) that provides a one-sentence summary of the paper.
        - A set of **initial keywords** from metadata (which may be empty or incomplete).

        Instructions:
        1. Carefully analyze the **abstract**, **conclusion** (if provided), and **TL;DR** (if provided) to understand the main topics, methods, and key findings.
        2. If the **conclusion** is missing, rely on the **abstract** and **TL;DR** to identify the core aspects of the paper.
        3. Use the **initial keywords** as a reference. You may:
        - Retain relevant keywords.
        - Modify or refine them if necessary.
        - Add new keywords based on the provided texts.
        4. Select keywords that best capture:
        - The main research problem and solution.
        - Key methods, models, or frameworks used or introduced.
        - Important application domains or use cases.
        - Novel contributions or unique technical terms.

        5. Guidelines for choosing keywords:
        - Use concise terms or short phrases (e.g., "transformer models", "graph neural networks", "multi-agent systems").
        - Avoid overly generic words (e.g., "study", "paper", "result") unless essential.
        - Exclude duplicates or semantically redundant keywords.
        - Provide **5 to 10 high-quality keywords** that best summarize the paper.

        Texts to analyze:
        TL;DR (if any):
        $tldr_text

        Initial keywords (if any):
        $initial_keywords

        Abstract (may be empty):
        $abstract_text

        Conclusion (may be empty):
        $conclusion_text

        Output requirements:
        - Return **only a JSON object** containing the final list of keywords.
        - **Do not** include explanations, comments, or extra information.
        - If you cannot find enough keywords, include as many valid ones as possible without guessing.

        Example output:
        {
        "keywords": [
            "large language models",
            "alignment techniques",
            "reinforcement learning from human feedback",
            "zero-shot generalization",
            "efficient model scaling"
        ]
        }
        """
    )
