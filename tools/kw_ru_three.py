# -*- coding: utf-8 -*-
"""Перевод первых трёх статей KeyWord. Строки ≤ 72 символа (как в оригинале)."""
import json

ARTICLES = [
    {
        "term_en": "Jupiter War",
        "term_ru": "Война за Юпитер",
        "series_en": "",
        "series_ru": "",
        "text_en": (
            "A war that broke out in UC 0133 between Jupiter Empire, Earth \n"
            "Federation, and the space pirates, Crossbone Vanguard.\n"
            "At the beginning of the war, when the Federation was unaware of the \n"
            "Jupiter Empire's actions, only Crossbone Vanguard realized what was \n"
            "truly happening and began to quietly make moves against them.\n"
            "However, after Dogatie declared a worldwide nuclear attack, the \n"
            "Colony forces, who were taking a cautious approach with regard to the \n"
            "Earth Federation Forces, decided to join the fight, a move which led \n"
            "to all-out war against Jupiter Empire.\n"
            "In the final stages of the war, the true Dogatie descended to Earth \n"
            "in the giant mobile armor Divinidad to pollute the planet with \n"
            "nuclear weapons. However, Tobia and Kincade pursued him, and put a \n"
            "stop to his plans. The war ended with the death of Supreme Leader \n"
            "Dogatie."
        ),
        "text_ru": (
            "Война, вспыхнувшая в 0133 году Вселенского века между Империей\n"
            "Юпитера, Федерацией Земли и космическими пиратами Кроссбоун-Вангард.\n"
            "В начале войны Федерация не подозревала о действиях Империи Юпитера,\n"
            "и лишь Кроссбоун-Вангард понял, что происходит на самом деле, и\n"
            "начал тайно действовать против неё.\n"
            "Однако после того, как Догати объявил о ядерном ударе по всему миру,\n"
            "колониальные силы, прежде осторожничавшие с войсками Федерации\n"
            "Земли, решили вступить в бой — и это переросло в тотальную войну\n"
            "против Империи Юпитера.\n"
            "На последнем этапе войны истинный Догати спустился к Земле в\n"
            "гигантском мобильном доспехе «Дивинидад», чтобы отравить планету\n"
            "ядерным оружием. Но Тобиа и Кинкейд настигли его и сорвали эти\n"
            "планы. Война закончилась гибелью верховного вождя Догати."
        ),
    },
    {
        "term_en": "Axis Shock",
        "term_ru": "Падение Акси",
        "series_en": "Mobile Suit Gundam: Char's Counterattack",
        "series_ru": "Мобильный воин Гандам: Контратака Чара",
        "text_en": "(см. оригинал)",
        "text_ru": (
            "Явление, произошедшее во время Второй войны Нео-Зеона (Мятежа Чара).\n"
            "Чар задумал сбросить астероид Акси на Землю, чтобы сделать её\n"
            "непригодной для жизни. Чтобы помешать этому, оперативное соединение\n"
            "«Лондо Белл» сумело расколоть Акси, но из-за силы взрыва один из\n"
            "обломков устремился к Земле.\n"
            "Амуро упёрся «Ню Гандамом» в Акси, уже вошедший в атмосферу Земли,\n"
            "пытаясь отвернуть его. В ответ машина испустила свет психорамы,\n"
            "который притянул находившиеся рядом силы, и те собрались вокруг\n"
            "падающего астероида. Преодолев вражду между Федерацией Земли и\n"
            "Нео-Зеоном, они упёрлись своими мобильными доспехами в Акси и\n"
            "вместе оттолкнули его.\n"
            "Разраставшийся свет психорамы вывел из строя все машины, кроме «Ню\n"
            "Гандама», и отбросил астероид прочь от Земли. Этот свет видели в\n"
            "разных уголках планеты, и он навсегда остался в памяти многих."
        ),
    },
    {
        "term_en": "100 Years Ago",
        "term_ru": "Сто лет назад",
        "series_en": "",
        "series_ru": "",
        "text_en": "(см. оригинал)",
        "text_ru": (
            "Сто лет назад, в 2100 году Нового правильного века, достигло пика\n"
            "противостояние землян и спейсноидов, начавшееся с Однолетней войны.\n"
            "Принято считать, что всему положил конец Мятеж Чара, но за ним\n"
            "последовало Потерянное десятилетие, от которого не сохранилось\n"
            "почти никаких записей. Многие полагают, что все эти десять лет\n"
            "антифедеральные организации продолжали теракты, пока войны не\n"
            "оборвал трагический Инцидент Муфтия. Но под натиском гамиласцев\n"
            "мало у кого есть время думать об истории, и то, что известно\n"
            "широкой публике, зачастую далеко от правды."
        ),
        "text2_ru": (
            "Позднейшие исследования показали, что «Потерянное десятилетие» было\n"
            "подлогом, задуманным правительством Федерации Земли, которое\n"
            "опасалось влияния Хартии Вселенского века."
        ),
    },
]

out = r"D:\games\SUPER ROBOT WARS V\_extracted\keywords_ru.json"
json.dump({"articles": ARTICLES}, open(out, "w", encoding="utf-8"), ensure_ascii=False, indent=1)

for a in ARTICLES:
    print("=" * 66)
    print(f'{a["term_en"]}  →  {a["term_ru"]}')
    if a["series_ru"]:
        print(f'  серия: {a["series_ru"]}')
    print(a["text_ru"])
    if a.get("text2_ru"):
        print("  [после прохождения]")
        print(a["text2_ru"])
    maxlen = max(len(l) for l in a["text_ru"].split("\n"))
    print(f"  (макс. длина строки: {maxlen})")
print("\nсохранено:", out)
