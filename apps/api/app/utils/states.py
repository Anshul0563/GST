STATE_CODES = {
    "01": "Jammu & Kashmir",
    "02": "Himachal Pradesh",
    "03": "Punjab",
    "04": "Chandigarh",
    "05": "Uttarakhand",
    "06": "Haryana",
    "07": "Delhi",
    "08": "Rajasthan",
    "09": "Uttar Pradesh",
    "10": "Bihar",
    "11": "Sikkim",
    "12": "Arunachal Pradesh",
    "13": "Nagaland",
    "14": "Manipur",
    "15": "Mizoram",
    "16": "Tripura",
    "17": "Meghalaya",
    "18": "Assam",
    "19": "West Bengal",
    "20": "Jharkhand",
    "21": "Odisha",
    "22": "Chhattisgarh",
    "23": "Madhya Pradesh",
    "24": "Gujarat",
    "26": "Dadra and Nagar Haveli and Daman and Diu",
    "27": "Maharashtra",
    "29": "Karnataka",
    "30": "Goa",
    "31": "Lakshadweep",
    "32": "Kerala",
    "33": "Tamil Nadu",
    "34": "Puducherry",
    "35": "Andaman and Nicobar Islands",
    "36": "Telangana",
    "37": "Andhra Pradesh",
    "38": "Ladakh",
    "97": "Other Territory",
}


def normalize_state_text(value: object) -> str:
    text = "" if value is None else str(value)
    text = text.strip().lower()
    text = text.replace("&", " and ")
    text = text.replace("-", " ")
    text = text.replace("_", " ")
    text = text.replace(".", " ")
    return " ".join(text.split())


STATE_NAME_TO_CODE = {normalize_state_text(value): key for key, value in STATE_CODES.items()}
ALIASES = {
    "andaman": "35",
    "andaman nicobar": "35",
    "andaman and nicobar": "35",
    "andaman and nicobar islands": "35",
    "ap": "37",
    "arunachal": "12",
    "chattisgarh": "22",
    "dadra": "26",
    "dadra and nagar haveli": "26",
    "dadra nagar haveli": "26",
    "dadra nagar haveli daman diu": "26",
    "daman": "26",
    "daman and diu": "26",
    "delhi": "07",
    "diu": "26",
    "dnh": "26",
    "dnhdd": "26",
    "hp": "02",
    "j and k": "01",
    "jammu and kashmir": "01",
    "jk": "01",
    "maharastra": "27",
    "mh": "27",
    "mp": "23",
    "nct delhi": "07",
    "new delhi": "07",
    "orissa": "21",
    "pondicherry": "34",
    "puducherry": "34",
    "tn": "33",
    "ts": "36",
    "ua": "05",
    "uk": "05",
    "up": "09",
    "ut": "05",
    "uttaranchal": "05",
    "wb": "19",
}

PIN_PREFIX_TO_STATE = {
    "11": "07",
    "12": "06",
    "13": "06",
    "14": "03",
    "15": "03",
    "16": "04",
    "17": "02",
    "18": "01",
    "19": "01",
    "20": "09",
    "21": "09",
    "22": "09",
    "23": "09",
    "24": "09",
    "25": "09",
    "26": "09",
    "27": "09",
    "28": "09",
    "30": "08",
    "31": "08",
    "32": "08",
    "33": "08",
    "34": "08",
    "36": "24",
    "37": "24",
    "38": "24",
    "39": "24",
    "40": "27",
    "41": "27",
    "42": "27",
    "43": "27",
    "44": "27",
    "45": "23",
    "46": "23",
    "47": "23",
    "48": "23",
    "49": "22",
    "50": "36",
    "51": "37",
    "52": "37",
    "53": "37",
    "56": "29",
    "57": "29",
    "58": "29",
    "59": "29",
    "60": "33",
    "61": "33",
    "62": "33",
    "63": "33",
    "64": "33",
    "67": "32",
    "68": "32",
    "69": "32",
    "70": "19",
    "71": "19",
    "72": "19",
    "73": "19",
    "74": "19",
    "75": "21",
    "76": "21",
    "77": "21",
    "78": "18",
    "79": "12",
    "80": "10",
    "81": "10",
    "82": "20",
    "83": "20",
    "84": "10",
    "85": "10",
}

PIN_EXACT_PREFIX_TO_STATE = {
    "682": "31",
    "737": "11",
    "744": "35",
    "795": "14",
    "796": "15",
    "797": "13",
    "798": "13",
    "799": "16",
}


def state_code_from_text(value: object) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    if not text:
        return None
    if text.isdigit():
        code = text.zfill(2)
        if code in STATE_CODES:
            return code
    if text[:2].isdigit() and text[:2] in STATE_CODES:
        return text[:2]
    lowered = normalize_state_text(text)
    if lowered in STATE_NAME_TO_CODE:
        return STATE_NAME_TO_CODE[lowered]
    return ALIASES.get(lowered)


def state_code_from_pincode(value: object) -> str | None:
    if value is None:
        return None
    digits = "".join(char for char in str(value) if char.isdigit())
    if len(digits) < 6:
        return None
    pin = digits[:6]
    return PIN_EXACT_PREFIX_TO_STATE.get(pin[:3]) or PIN_PREFIX_TO_STATE.get(pin[:2])
