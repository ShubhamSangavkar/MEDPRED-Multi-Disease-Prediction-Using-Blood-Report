
import re

FEATURE_ALIASES = {
    "alb": ["alb", "albumin", "serum albumin", "s. albumin", "serum alb", "serum albumin level", "Serum Albumin td g/dL","ALBUMIN - SERUM PHOTOMETRY"],
    "alkphos": ["alkphos", "alp", "alkp", "alk phos", "alkaline phosphatase", "serum alp", "serum alkaline phosphatase", "serum alkaline phosphatse", "rs S. Alkaline Phosphatase","ALKALINE PHOSPHATASE PHOTOMETRY"],
    "sgpt": ["sgpt", "s.g.p.t.", "alt", "alanine transaminase", "alanine aminotransferase", "serum alt", "serum sgpt", "serum sgpt (alt)", "sgpt (alt)","ALANINE TRANSAMINASE (SGPT) PHOTOMETRY"],
    "sgot": ["sgot", "s.g.o.t.", "ast", "aspartate transaminase", "aspartate aminotransferase", "serum ast", "serum sgot", "serum sgot (ast)", "sgot (ast)","ASPARTATE AMINOTRANSFERASE (SGOT ) PHOTOMETRY"],
    "tb": ["tb", "tbil", "total bilirubin", "t. bilirubin", "serum bilirubin total", "bilirubin total", "serum bilirubin, total", "serum bilirubin total level", "en S. Bilirubin (Total)","BILIRUBIN - TOTAL PHOTOMETRY"],
    "tp": ["tp", "total protein", "serum total protein", "t. protein", "protein total", "serum total protein level", "Serum Total Protein tte g/dL", "Serum Total Protein t"],
    "hba1c": ["hba1c", "hb a1c", "hb-a1c", "hb a1c%", "glycated hemoglobin", "glycosylated hemoglobin", "glycated haemoglobin", "glycosylated haemoglobin", "hemoglobin a1c", "haemoglobin a1c", "glycohemoglobin", "a1c", "al HbAlc", "Hb A","HbA1c H.P.L.C"],
    "glucose_level": ["glucose_level", "glucose", "blood glucose", "blood glucose level", "blood sugar", "blood sugar level", "blood glucose random", "random blood glucose", "random blood sugar", "rbs", "random blood sugar level", "fasting blood glucose", "fasting blood sugar", "fasting blood glucose level", "fasting blood sugar level", "fbs", "plasma glucose", "fasting plasma glucose", "random plasma glucose", "serum glucose", "Estimated mean blood glucose","AVERAGE BLOOD GLUCOSE (ABG) CALCULATED","90 Day Average Blood Glucose"],
    "sg": ["sg", "specific gravity", "urine specific gravity", "urine sg", "urinary specific gravity", "specific gravity urine", "urine specific gravity test", "urine sp gr", "sp gr", "sp. gr.", "urine sp. gr.", "specific gravity of urine", "urinalysis specific gravity", "urine gravity", "sg urine", "urine density", "urinary sg", "specific gravity (sg)", "sg (specific gravity)", "urine specific gravity level", "urine specific gravity value", "urine specific gravity reading", "urine gravity test", "urinalysis sg", "urine sp gravity", "urine specific-gravity", "specific-gravity urine", "urine specific gravity result", "urine sg level", "urine sg value"],
    "al": ["al", "urine albumin", "urine albumin level", "albumin in urine", "urinary albumin", "urine protein", "urinary protein", "urine albumin test", "urine albumin concentration", "albumin urine", "urine alb", "urinary alb", "albumin (urine)", "urine albumin value", "urine albumin result", "urine albumin reading", "urine protein level", "urinary albumin level", "urine protein concentration", "urine protein test", "albuminuria", "urine albumin measurement", "urinary albumin test", "albumin in the urine", "urine microalbumin", "urinary microalbumin", "microalbumin urine", "urine albumin finding", "urine albumin result value", "urine al"],
    "bu": ["bu", "blood urea", "serum urea", "urea", "blood urea level", "blood urea nitrogen", "bun", "serum blood urea", "urea in blood", "blood urea test", "serum urea level", "blood urea concentration", "urea concentration", "blood urea value", "blood urea result", "blood urea measurement", "urea blood test", "serum urea concentration", "blood urea reading", "blood urea parameter", "blood urea indicator", "blood urea nitrogen level", "bun level", "bun test", "serum bun", "blood bun", "urea level in blood", "blood urea nitrogen test", "blood urea result value", "bu level"],
    "sc": ["sc", "serum creatinine", "creatinine", "serum creatinine level", "blood creatinine", "serum creat", "creatinine serum", "serum creatinine test", "creatinine level", "blood creatinine level", "serum creatinine concentration", "creatinine in blood", "serum creatinine value", "serum creatinine result", "creatinine measurement", "serum creatinine reading", "serum creatinine concentration level", "creatinine blood test", "serum creatinine test result", "blood creatinine test", "serum creatinine measurement", "serum creatinine parameter", "creatinine serum level", "serum creatinine findings", "serum creatinine value level", "serum creatinine result value", "serum creatinine reading value", "sc level", "sc test", "serum cr"],
    "sod": ["sod", "sodium", "serum sodium", "serum sodium level", "blood sodium", "blood sodium level", "sodium serum", "serum sodium test", "sodium level", "sodium concentration", "serum sodium concentration", "sodium in blood", "serum sodium value", "serum sodium result", "sodium blood test", "sodium measurement", "serum sodium reading", "blood sodium concentration", "sodium test result", "serum sodium measurement", "sodium serum level", "serum na", "na", "na+", "serum na+", "sodium ion", "sodium electrolyte", "serum sodium parameter", "sodium result value", "sod level"],
    "pot": ["pot", "potassium", "serum potassium", "serum potassium level", "blood potassium", "blood potassium level", "potassium serum", "serum potassium test", "potassium level", "potassium concentration", "serum potassium concentration", "potassium in blood", "serum potassium value", "serum potassium result", "potassium blood test", "potassium measurement", "serum potassium reading", "blood potassium concentration", "potassium test result", "serum potassium measurement", "potassium serum level", "serum k", "k", "k+", "serum k+", "potassium ion", "potassium electrolyte", "serum potassium parameter", "potassium result value", "pot level"],
    "hemo": ["hemo", "hemoglobin", "haemoglobin", "hb", "hemoglobin level", "haemoglobin level", "blood hemoglobin", "blood haemoglobin", "serum hemoglobin", "hemoglobin test", "haemoglobin test", "hemoglobin concentration", "haemoglobin concentration", "hb level", "hb concentration", "hemoglobin value", "haemoglobin value", "hemoglobin result", "haemoglobin result", "blood hb", "hemoglobin measurement", "haemoglobin measurement", "hemoglobin reading", "haemoglobin reading", "hemoglobin in blood", "haemoglobin in blood", "hb test", "hb result", "hemoglobin count", "haemoglobin count"]
}

def normalize_name(name):
    return re.sub(r"[^a-z0-9]", "", name.lower())


ALIAS_LOOKUP = {}

for standard_name, aliases in FEATURE_ALIASES.items():
    for alias in aliases + [standard_name]:
        key = normalize_name(alias)

        if key in ALIAS_LOOKUP and ALIAS_LOOKUP[key] != standard_name:
            raise ValueError(f"Conflicting alias: {alias}")

        ALIAS_LOOKUP[key] = standard_name


def standardize_tests(tests):
    features = []
    unmatched_tests = []

    for test in tests:
        original_name = str(test.get("test_name", "")).strip()
        key = normalize_name(original_name)
        standard_name = ALIAS_LOOKUP.get(key)

        if standard_name:
            item = test.copy()
            item["original_test_name"] = original_name
            item["test_name"] = standard_name
            features.append(item)
        else:
            unmatched_tests.append(original_name)

    return {
        "features": features,
        "unmatched_tests": unmatched_tests
    }
