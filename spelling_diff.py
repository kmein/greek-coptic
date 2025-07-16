from difflib import SequenceMatcher
import itertools
import math
import os
import pandas as pd
import re
import unicodedata

greek_to_coptic = {
  'α': 'ⲁ',
  'β': 'ⲃ',
  'γ': 'ⲅ',
  'δ': 'ⲇ',
  'ε': 'ⲉ',
  'ζ': 'ⲍ',
  'η': 'ⲏ',
  'θ': 'ⲑ',
  'ϑ': 'ⲑ',
  'ι': 'ⲓ',
  'κ': 'ⲕ',
  'λ': 'ⲗ',
  'μ': 'ⲙ',
  'ν': 'ⲛ',
  'ξ': 'ⲝ',
  'ο': 'ⲟ',
  'π': 'ⲡ',
  'ρ': 'ⲣ',
  'σ': 'ⲥ',
  'τ': 'ⲧ',
  'υ': 'ⲩ',
  'φ': 'ⲫ',
  'χ': 'ⲭ',
  'ψ': 'ⲯ',
  'ω': 'ⲱ',
  'ς': 'ⲥ',
  'ϗ': 'ⳤ',
  '\u0314': 'ϩ',
  '\u0345': 'ⲓ',
}

consonants = set("ⲡ ⲧ ⲕ ⲃ ⲇ ⲅ ⲫ ⲑ ⲭ ϩ ⲥ ϣ ϥ ϫ ϭ ⲗ ⲣ ⳉ ϧ ⲛ ⲙ ⲍ ⲝ ⲯ".split())

vowels = set("ⲁ ⲉ ⲏ ⲓ ⲟ ⲱ ⲩ".split())

diphthongs = set("ⲁⲓ ⲉⲓ ⲏⲓ ⲟⲓ ⲩⲓ ⲱⲓ ⲁⲩ ⲉⲩ ⲟⲩ ⲏⲩ".split())

greek_to_coptic_ord = {ord(greek): ord(coptic) for greek, coptic in greek_to_coptic.items()}

def unify_date(row):
    max_date_distance = 200
    if not math.isnan(row["latest"]) and not math.isnan(row["earliest"]) and row["latest"] - row["earliest"] <= max_date_distance:
        return (row["latest"]+row["earliest"])/2
    else:
        return None

### FIND DEVIATIONS

def transliterate(greek):
    normalized = unicodedata.normalize("NFD", greek)
    clean_spiritus_asper = lambda x: re.sub(r"^([ⲣⲁⲉⲏⲓⲟⲱⲩ]+)ϩ", r'ϩ\1', x)
    return clean_spiritus_asper(
        "".join(
            greek_to_coptic[character.lower()]
            for character in normalized
            if character.lower() in greek_to_coptic
        )
    )

def get_required_edits(a, b):
    for operation, a_start, a_end, b_start, b_end in SequenceMatcher(
        a=a, b=b, autojunk=False
    ).get_opcodes():
        the_input = a[a_start:a_end]
        if len(the_input) == 0: the_input = "∅"
        the_output = b[b_start:b_end]
        if len(the_output) == 0: the_output = "∅"

        context_left = a[:a_start]
        if len(context_left) == 0: context_left = "#"
        context_right = a[a_end:]
        if len(context_right) == 0: context_right = "#"
        if operation == "equal": continue
        yield {"operation": operation, "norm": the_input, "var": the_output, "context_left": context_left, "context_right": context_right}

remove_null = lambda x: x.replace("∅", "") if len(x) > 1 else x

group_cv = lambda string: [(b, "".join(cs)) for b, cs in itertools.groupby(string.replace("∅", ""), key=lambda x: x in vowels)]

unzip = lambda xs: zip(*xs) if xs else ([], [])

def fix_CV_or_VC(edit):
    try:
        input_booleans, input_cv_groups = unzip(group_cv(edit["norm"]))
        output_booleans, output_cv_groups = unzip(group_cv(edit["var"]))
        if input_booleans == output_booleans and len(input_booleans) > 1:
            edits = []
            position = 0
            context_left = ""
            context_right = "".join(input_cv_groups)
            for input_cv, output_cv in zip(input_cv_groups, output_cv_groups, strict=True):
                position += len(input_cv)
                edits.append({
                    "norm": "".join(input_cv),
                    "var": "".join(output_cv),
                    "context_left": remove_null(edit["context_left"] + context_left),
                    "context_right": remove_null(context_right[position:] + edit["context_right"])
                })
                context_left += "".join(input_cv)
            return edits
        elif (input_booleans == (True,) and output_booleans == (True, False)) or (input_booleans == (False,) and output_booleans == (False, True)):
            # insertion to the right
            print("insertion right", input_cv_groups, output_cv_groups)
            return [{
                "norm": input_cv_groups[0],
                "var": output_cv_groups[0],
                "context_left": remove_null(edit["context_left"]),
                "context_right": remove_null(edit["context_right"])
            }, {
                "norm": "∅",
                "var": output_cv_groups[1],
                "context_left": remove_null(edit["context_left"] + input_cv_groups[0]),
                "context_right": remove_null(edit["context_right"])
            }]
        elif (input_booleans == (True,) and output_booleans == (False, True)) or (input_booleans == (False,) and output_booleans == (True, False)):
            # insertion to the left
            print("insertion left", input_cv_groups, output_cv_groups)
            return [{
                "norm": "∅",
                "var": output_cv_groups[0],
                "context_left": remove_null(edit["context_left"]),
                "context_right": remove_null(input_cv_groups[0] + edit["context_right"])
            }, {
                "norm": input_cv_groups[0],
                "var": output_cv_groups[1],
                "context_left": remove_null(edit["context_left"]),
                "context_right": remove_null(edit["context_right"])
            }]
        else:
            return [edit]
    except ValueError:
        return [edit]

def fix_insert_h(edit):
    input_booleans, _ = unzip(group_cv(edit["norm"]))
    output_booleans, _ = unzip(group_cv(edit["var"]))
    if edit["context_left"] == "#" and len(output_booleans) > len(input_booleans) and edit["var"].startswith("ϩ"):
        return [{
            "norm": edit["norm"],
            "var": edit["var"].removeprefix("ϩ"),
            "context_left": edit["context_left"],
            "context_right": edit["context_right"]
        }, {
            "norm": "∅",
            "var": "ϩ",
            "context_left": edit["context_left"],
            "context_right": edit["norm"] + edit["context_right"]
        }]
    else:
        return [edit]

def fix_degemination(edit):
    input_booleans, _ = unzip(group_cv(edit["norm"]))
    output_booleans, _ = unzip(group_cv(edit["var"]))
    if input_booleans == output_booleans:
        return [edit]
    if edit["var"] == "∅":
        if edit["context_left"].endswith(edit["norm"]):
            geminate = edit["norm"]
            return [{
                "norm": geminate * 2,
                "var": geminate,
                "context_left": edit["context_left"].removesuffix(geminate),
                "context_right": edit["context_right"]
            }]
        elif edit["context_right"].startswith(edit["norm"]):
            geminate = edit["norm"]
            return [{
                "norm": geminate * 2,
                "var": geminate,
                "context_left": edit["context_left"],
                "context_right": edit["context_right"].removeprefix(geminate)
            }]
        else:
            return [edit]
    elif edit["context_left"].endswith(edit["norm"][0]):
        geminate = edit["norm"][0]
        return [{
            "norm": edit["norm"].removeprefix(geminate),
            "var": edit["var"],
            "context_left": edit["context_left"] + geminate,
            "context_right": edit["context_right"]
        }, {
            "norm": geminate * 2,
            "var": geminate,
            "context_left": edit["context_left"].removesuffix(geminate),
            "context_right": edit["norm"].removeprefix(geminate)+ edit["context_right"],
        }]
    elif edit["context_right"].startswith(edit["norm"][-1]):
        geminate = edit["norm"][-1]
        return [{
            "norm": edit["norm"].removesuffix(geminate),
            "var": edit["var"],
            "context_left": edit["context_left"],
            "context_right": geminate + edit["context_right"]
        }, {
            "norm": geminate * 2,
            "var": geminate,
            "context_left": edit["norm"].removesuffix(geminate),
            "context_right": edit["context_right"].removeprefix(geminate),
        }]
    else:
        return [edit]

def fix_gemination(edit):
    input_booleans, _ = unzip(group_cv(edit["norm"]))
    output_booleans, _ = unzip(group_cv(edit["var"]))
    if input_booleans == output_booleans:
        return [edit]
    if edit["norm"] == "∅":
        if edit["context_left"].endswith(edit["var"]):
            geminate = edit["var"]
            return [{
                "norm": geminate,
                "var": geminate * 2,
                "context_left": edit["context_left"].removesuffix(geminate),
                "context_right": edit["context_right"]
            }]
        elif edit["context_right"].startswith(edit["var"]):
            geminate = edit["var"]
            return [{
                "norm": geminate,
                "var": geminate * 2,
                "context_left": edit["context_left"],
                "context_right": edit["context_right"].removeprefix(geminate)
            }]
        else:
            return [edit]
    elif edit["context_left"].endswith(edit["var"][0]):
        geminate = edit["var"][0]
        return [{
            "norm": edit["norm"],
            "var": edit["var"].removeprefix(geminate),
            "context_left": edit["context_left"],
            "context_right": edit["context_right"]
        }, {
            "norm": geminate,
            "var": geminate * 2,
            "context_left": edit["context_left"].removesuffix(geminate),
            "context_right": edit["norm"]+edit["context_right"],
        }]
    elif edit["context_right"].startswith(edit["var"][-1]):
        geminate = edit["var"][-1]
        return [{
            "norm": edit["norm"],
            "var": edit["var"].removesuffix(geminate),
            "context_left": edit["context_left"],
            "context_right": edit["context_right"]
        }, {
            "norm": geminate,
            "var": geminate * 2,
            "context_left": edit["norm"],
            "context_right": edit["context_right"].removeprefix(geminate)
        }]
    else:
        return [edit]

protected_digraphs = {
    "ⲁⲓ": "ä",
    "ⲉⲓ": "ë",
    "ⲏⲓ": "ḧ",
    "ⲟⲓ": "ö",
    "ⲩⲓ": "ü",
    "ⲱⲓ": "ẅ",
    "ⲁⲩ": "â",
    "ⲉⲩ": "ê",
    "ⲟⲩ": "ô",
    "ⲏⲩ": "ĥ",
    "ⲱⲩ": "ŵ",
}

def protect_digraphs(string):
    result = string
    for digraph, code in protected_digraphs.items():
        result = result.replace(digraph, code)
    return result

def unprotect_digraphs(string):
    result = string
    for digraph, code in protected_digraphs.items():
        result = result.replace(code, digraph)
    return result

def unprotect_edit(edit):
    return {
        "norm": unprotect_digraphs(edit["norm"]),
        "var": unprotect_digraphs(edit["var"]),
        "context_left": unprotect_digraphs(edit["context_left"]),
        "context_right": unprotect_digraphs(edit["context_right"])
    }

def flatmap(func, *iterable):
    return itertools.chain.from_iterable(map(func, *iterable))

def get_required_edits_improved(x, y):
    return flatmap(fix_CV_or_VC,
            flatmap(fix_degemination,
                flatmap(fix_gemination,
                    map(unprotect_edit,
                        get_required_edits(
                            protect_digraphs(x),
                            protect_digraphs(y)
                        )
                    )
                )
            )
        )


def main():
    df = pd.read_csv(os.getenv("ATTESTATIONS_CSV") or "ddglc-attestations.csv") \
        .set_index("id") \
        .drop(columns=["dialect"]) \
        .rename(columns={"code": "dialect"})

    df["dialect_group"] = df["dialect_group"].replace({
        "Akhmimic Dialects": "A",
        "Lycopolitan Dialects": "L",
        "Middle Egyptian Dialects": "M",
        "Sahidic Dialects": "S",
        "Bohairic Dialects": "B",
        "Fayyumic Dialects": "F"
    })

    df["date_approximate"] = df.apply(unify_date, axis=1)
    df['century'] = (df['date_approximate'] // 100) + 1

    df.dropna(subset={"orthography", "greek_lemma"}, inplace=True)

    df = df[~(
        df["orthography"].str.contains("sic")
        | df["orthography"].str.endswith(("/", "/̅", "/°")) # remove marked abbreviations
        | df["orthography"].str.contains(r"\d|[….ⳇ⁄?ⳁ⳨Ⳁ⳧ⲋ⳦⳥⳽]", regex=True) # remove lines with numbers or marked abbreviations
    )]

    df["orthography_clean"] = (
        df["orthography"]
        .str.strip() # remove extraneous whitespace
        .str.lower() # convert capital letters to lower case
        .apply(lambda x: x.translate(greek_to_coptic_ord)) # convert Greek letters that crept in
        .str.replace("ϊ", "ⲓ") # convert precombined accented greek letter
        .str.replace("[\u0305\u0304\ufe24\ufe25\ufe26\u2cf1\u2cf0\u0300]+", "", regex=True) # remove overlines
        .str.replace("[\u2CBB\u2CEF]", "ⲛ", regex=True) # normalize letter ⲛ (written as stroke)
        .str.replace("[ⳅⲹ]", "ⲍ", regex=True) # normalize letter ⲍ
        .str.replace("o", "ⲟ") # replace latin o by coptic
        .str.replace("\u001D|\u0314|\u200E|\u0486|\u02BE|\u2CFF|\u0307|\u0308|\u0301|\u0323|\u0304|\u1DCD|\u0302|\u0306" + "|" + r"col\.b|/|⟦.*?⟧|\\|\[|\]|[‖|´⸤⸥⸢⸣⁅⁆⸖'‹›`’`´:⸌⸍\⸳‧·•·ʾ*]", "", regex=True)
    )

    df["greek_lemma_original"] = df["greek_lemma"]
    df["greek_lemma"] = df["greek_lemma_original"].apply(transliterate)

    df["accuracy"] = df.apply(lambda row: SequenceMatcher(None, row["greek_lemma"], row["orthography_clean"]).ratio(), axis=1)

    df_diff = df.apply(
        lambda row: list(get_required_edits_improved(row["greek_lemma"], row["orthography_clean"])),
        axis=1
    ).explode().dropna()
    df_diff = pd.DataFrame(df_diff.tolist(), index=df_diff.index)
    df_diff = df_diff.merge(df[["greek_lemma", "greek_lemma_original", "orthography", "orthography_clean", "dialect", "dialect_group", "manuscript_text", "date_approximate", "earliest", "latest", "century"]], on="id")
    df_diff = df_diff[df_diff["greek_lemma"].str.len() > 0]

    # remove verbal endings
    df_diff = df_diff[~(
        (
            df_diff["norm"].str.endswith(("ⲱ", "ⲟⲙⲁⲓ", "ⲙⲓ"))
        ) & (
            df_diff["context_right"] == "#"
        )
    ) & ~( # remove stuff like ⲭⲟⲣⲉⲱ → ⲭⲟⲣⲉⲩⲉ
        (df_diff["context_right"] == "ⲉⲱ")
        & (df_diff["norm"] == "∅")
        & (df_diff["var"] == "ⲉⲩ")
    )]

    # remove nominal morphology
    df_diff = df_diff[~(
        (df_diff["context_right"].isin({"#", "ⲥ","ⲛ"}))
        & (
            (df_diff["norm"].isin({"ⲥ", "ⲛ"}) & df_diff["var"].isin({"ⲛ", "ⲩ"}) & df_diff["context_left"].str.endswith("ⲟ"))
            | ((df_diff["norm"] == "ⲟ") & (df_diff["var"].isin({"ⲏ", "ⲁ", "ⲱ", "ⲟⲓ", "ⲉ", "ⲟⲩ"})))
            | ((df_diff["norm"] == "ⲩ") & (df_diff["var"] == "ⲏ"))
            | ((df_diff["norm"] == "ⲥ") & (df_diff["var"] == "ⲛ"))
            | ((df_diff["norm"].isin({"ⲛ","∅", "ⲥ"})) & (df_diff["var"].isin({"ⲥ", "ⲛ", "∅"})))
            | ((df_diff["norm"] == "ⲏ") & (df_diff["var"] == "ⲟⲟⲩⲉ"))
        )
    ) & ~(
        (df_diff["context_right"] == "ⲥ")
        & (
            ((df_diff["norm"] == "ⲟ") & (df_diff["var"] == "ⲏ"))
            | ((df_diff["norm"] == "ⲏ") & (df_diff["var"] == "ⲟ"))
        )
    ) & ~(
        (df_diff["context_left"] == "#")
        & (
            ((df_diff["norm"] == "ϩ") & df_diff["var"].isin({"ⲫ", "ⲑ"}))
            | ((df_diff["norm"] == "∅") & (df_diff["var"].isin({"ⲑ", "ⲧⲟⲥ"})))
        )
    ) & ~(
        ((df_diff["norm"] == "ⲩ") & (df_diff["var"] == "ⲓ") & (df_diff["greek_lemma"] == "ⲉⲗⲁⲭⲩⲥ"))
        | ((df_diff["norm"] == "ⲟⲥ") & (df_diff["var"] == "∅") & (df_diff["greek_lemma"] == "ⲓⲟⲩⲇⲁⲓⲟⲥ"))
        | ((df_diff["norm"] == "ⲥ") & (df_diff["var"] == "ⲑ") & (df_diff["greek_lemma"] == "ⲡⲣⲁⲥⲥⲱ"))
        | ((df_diff["norm"] == "ϩ") & (df_diff["var"] == "ⲧ") & (df_diff["greek_lemma"].isin({"ϩⲟⲩⲧⲟⲥ", "ϩⲟ", "ϩⲏ"})))
    )]

    # remove adverbial endings
    df_diff = df_diff[~(
        (df_diff["context_right"] == "ⲥ")
        & (df_diff["norm"].isin({"ⲟ", "ⲏ"}) & (df_diff["var"] == "ⲱ"))
    )]

    blacklist = {
        ""
        "ⲡⲛⲉⲩⲙⲁ",
        "ⲭⲣⲓⲥⲧⲟⲥ", "ⲭⲣⲏⲥⲧⲟⲥ",
        "ⲥⲧⲁⲩⲣⲟⲥ", "ⲥⲧⲁⲩⲣⲟⲱ",
        "ⲥⲱⲧⲏⲣ",
        "ⲡⲛⲉⲩⲙⲁⲧⲓⲕⲟⲥ",
        "ⲇⲉⲓⲛⲁ",
        "ⲕⲩⲣⲓⲟⲥ",
        "ⲡⲁⲛⲧⲟⲕⲣⲁⲧⲱⲣ",
        "ⲁⲙⲏⲛ" # sometimes ϥⲑ
    }

    # remove common abbreviations
    df_diff = df_diff[~(
        (df_diff["var"] == "∅") & df_diff["greek_lemma"].isin(blacklist)
    )]

    df.to_csv('attestations.csv')
    df_diff.to_csv('deviations.csv')

if __name__ == "__main__":
    main()
