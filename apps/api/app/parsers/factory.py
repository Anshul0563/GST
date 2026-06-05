from app.parsers.amazon import AmazonParser
from app.parsers.custom import CustomExcelParser
from app.parsers.flipkart import FlipkartParser
from app.parsers.meesho import MeeshoParser


PARSERS = {
    "amazon": AmazonParser,
    "flipkart": FlipkartParser,
    "meesho": MeeshoParser,
    "myntra": CustomExcelParser,
    "jiomart": CustomExcelParser,
    "snapdeal": CustomExcelParser,
    "custom": CustomExcelParser,
}


def get_parser(platform: str):
    normalized = platform.lower()
    parser = PARSERS.get(normalized, CustomExcelParser)
    if parser is CustomExcelParser and normalized != "custom":
        return type(
            f"{normalized.title().replace('-', '')}Parser",
            (CustomExcelParser,),
            {"platform": normalized},
        )
    return parser
