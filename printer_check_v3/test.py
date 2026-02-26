def parse_gs1_string(raw: str):
    """
    Жёсткий парсер под формат Честного ЗНАКа:
    (01)14 цифр + (21)до 20 символов + (91) + (92)
    """
    ai_list = []
    if raw.startswith("01"):
        gtin = raw[2:16]
        ai_list.append(("01", gtin))
        pos = 16
    else:
        return []

    if raw[pos:pos+2] == "21":
        pos += 2
        # серийник идёт до "91"
        next_ai = raw.find("91", pos)
        serial = raw[pos:next_ai]
        ai_list.append(("21", serial))
        pos = next_ai
    if raw[pos:pos+2] == "91":
        pos += 2
        val91 = raw[pos:pos+4]  # у тебя всегда "EE11"
        ai_list.append(("91", val91))
        pos += 4
    if raw[pos:pos+2] == "92":
        pos += 2
        val92 = raw[pos:]
        ai_list.append(("92", val92))

    return ai_list

def generate_gs1dm(ai_list, out_file):
    data = "".join(f"({ai}){val}" for ai, val in ai_list)
    img = treepoem.generate_barcode(barcode_type="gs1datamatrix", data=data)
    img.convert("RGB").save(out_file)
    return out_file
