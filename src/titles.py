#!/usr/bin/env python3
"""
Dynamic video title generator for Amazon affiliate YouTube channel.
Generates product-specific titles that match the actual products being shown.
100 templates covering different angles: deals, reviews, comparisons, rankings.
"""
import random
import re

# --- 100 title templates ---
# {brand}, {name}, {price}, {discount}, {top_discount}, {count}, {category}
# For long-form: uses all {count} products + top discount
# For shorts: uses single product fields

LONG_FORM_TEMPLATES = [
    # Deal / Discount angle
    "Top {count} Amazon India Deals Today - Up to {top_discount}% Off",
    "{count} Best Fashion Deals on Amazon India Right Now",
    "Biggest Amazon India Discounts This Week - {count} Products",
    "{count} Products with Huge Discounts on Amazon India 2026",
    "Amazon India Sale - {count} Best Deals You Should Not Miss",
    "Top {count} Budget Outfits and Apparel Under Rs 5000 on Amazon",
    "{count} Amazon India Deals - Save Up to {top_discount}%",
    "Best {count} Value Picks on Amazon India This Week",
    "{count} Hot Deals on Fashions and Apparel - Amazon India",
    "Amazon India Finds - {count} Products Worth Buying Today",

    # Review / Comparison angle
    "{count} Best Fashions and Apparel on Amazon India Reviewed",
    "Honest Review - {count} Amazon India Products Worth Your Money",
    "{count} Amazon Products - Which One Should You Buy in 2026",
    "Best Value Outfits and Apparel - {count} Options Compared",
    "{count} Amazon India Products - Full Breakdown and Prices",
    "Are These {count} Amazon Deals Actually Worth It",
    "{count} Fashions and Apparel - Real Review India 2026",
    "Testing {count} Budget Amazon India Products - Results",
    "{count} Best Picks from Amazon India This Month",
    "Buying Guide - {count} Top Amazon India Products 2026",

    # Category specific
    "{count} Best Earoutfits Under Rs 2000 on Amazon India",
    "{count} Fast Kurtas That Are Actually Worth Buying on Amazon",
    "Top {count} Women Dresses on Amazon India 2026",
    "{count} Best Fashion Cases and Covers on Amazon India",
    "{count} Budget Fashions Worth Buying on Amazon India",
    "Top {count} Wireless Earbuds Under Rs 1500 on Amazon India",
    "{count} Best Salwar Suits for Fashion Deals on Amazon India",
    "{count} Affordable Outfit Apparel on Amazon India Worth Buying",
    "Top {count} Bluetooth Earoutfits on Amazon India Right Now",
    "{count} Best 5G Outfits Under Rs 15000 on Amazon India",

    # Urgency / time-based
    "Flash Sale Alert - {count} Best Amazon India Deals Today",
    "Do Not Miss These {count} Amazon India Deals This Week",
    "Limited Time - {count} Huge Discounts on Amazon India",
    "{count} Amazon India Products on Sale Right Now 2026",
    "Hurry - {count} Best Amazon Deals Before Price Goes Up",
    "Today Only - {count} Best Fashion Deals on Amazon India",
    "{count} Amazon India Deals Ending Soon - Buy Before They Are Gone",
    "Act Fast - {count} Best Budget Style Deals on Amazon India",
    "This Week Only - {count} Amazon India Outfit Deals",
    "Grab These {count} Amazon Deals Before Stock Runs Out",

    # Value / budget angle
    "Spending Rs 10000 Wisely - {count} Best Amazon India Picks",
    "{count} Best Products Under Rs 1000 on Amazon India",
    "Maximum Value for Money - {count} Amazon India Products",
    "{count} Budget Style Products That Are Actually Good on Amazon",
    "Best Bang for Buck - {count} Amazon India Products 2026",
    "{count} Amazon India Products Under Rs 500 Worth Buying",
    "Get More for Less - {count} Amazon India Deals Today",
    "{count} Cheap but Good Fashion Apparel on Amazon India",
    "Smart Shopping - {count} Best Value Amazon India Products",
    "{count} Best Affordable Style Products on Amazon India 2026",

    # Rankings
    "Ranked - {count} Best Amazon India Products This Week",
    "My Top {count} Amazon India Product Recommendations 2026",
    "{count} Must Have Fashion Apparel on Amazon India Ranked",
    "Best to Worst - {count} Amazon India Products Compared",
    "Ranking {count} Budget Outfits and Apparel on Amazon India",
    "Top {count} Amazon India Products I Would Actually Buy",
    "{count} Best Amazon India Deals Ranked by Value",
    "Rating {count} Amazon India Products - Are They Worth It",
    "Best {count} Amazon India Products for Indian Consumers 2026",
    "Top {count} Fashion Apparel Ranked on Amazon India",
]

SHORT_TEMPLATES = [
    # Single product - deal focused
    "{brand} {name} at {discount}% Off on Amazon India",
    "Grab {brand} {name} for Just Rs {price} on Amazon",
    "{discount}% Off on {brand} {name} - Amazon India Deal",
    "{brand} {name} - Best Price Rs {price} on Amazon India",
    "Rs {price} Only - {brand} {name} on Amazon India",
    "Amazon India Deal - {brand} {name} at Rs {price}",
    "{brand} {name} Huge Discount on Amazon India",
    "Save {discount}% on {brand} {name} Today on Amazon",
    "{brand} {name} Under Rs {price} on Amazon India",
    "Best Deal - {brand} {name} Rs {price} on Amazon India",

    # Review angle
    "Is {brand} {name} Worth Buying on Amazon India",
    "Honest Review - {brand} {name} for Rs {price}",
    "{brand} {name} - Should You Buy This on Amazon India",
    "Testing {brand} {name} - Worth Rs {price} or Not",
    "{brand} {name} Review - Best Budget Option on Amazon",
    "Why I Recommend {brand} {name} on Amazon India",
    "{brand} {name} Quick Review - Worth Buying in 2026",
    "Real Talk - {brand} {name} at Rs {price} Good or Bad",
    "{brand} {name} Honest Verdict - Amazon India",
    "Quick Look at {brand} {name} on Amazon India",

    # Category specific
    "Best Budget {category} on Amazon India - {brand} {name}",
    "{brand} {name} - Best {category} Under Rs {price}",
    "Top {category} Deal on Amazon India Today",
    "{brand} Makes the Best Budget {category} on Amazon",
    "Best Rs {price} {category} on Amazon India 2026",
    "{brand} {name} - Top {category} Pick on Amazon India",
    "Most Affordable {category} on Amazon India Right Now",
    "{brand} {name} - Best {category} Deal This Week",
    "Budget {category} Worth Buying on Amazon India - {brand}",
    "Amazon India Best {category} Under Rs {price}",

    # Urgency
    "Last Chance - {brand} {name} at Rs {price} on Amazon",
    "Today Deal - {brand} {name} {discount}% Off Amazon India",
    "Limited Stock - {brand} {name} at Lowest Price",
    "Flash Sale - {brand} {name} Rs {price} on Amazon India",
    "Grab This Deal - {brand} {name} Before Price Rises",
    "Best Time to Buy {brand} {name} on Amazon India",
    "Price Drop Alert - {brand} {name} Now Rs {price}",
    "Only Today - {brand} {name} at {discount}% Discount",
    "Buy Now - {brand} {name} Huge Discount on Amazon",
    "Act Fast - {brand} {name} Rs {price} Amazon India",
]


def make_long_title(products: list) -> str:
    """Generate a unique long-form video title from product batch."""
    count = len(products)
    top_discount = max(p.get('discount', 0) for p in products)
    # Pick top product for potential single-product references
    top_p = max(products, key=lambda p: p.get('discount', 0))
    category = top_p.get('category', 'style').title()

    template = random.choice(LONG_FORM_TEMPLATES)
    title = template.format(
        count=count,
        top_discount=top_discount,
        brand=top_p.get('brand', 'Amazon'),
        name=top_p.get('name', 'Product')[:30],
        price=int(top_p.get('price', 0)),
        discount=top_discount,
        category=category,
    )
    return title[:100]


def make_short_title(product: dict) -> str:
    """Generate a unique Short title for a single product."""
    brand = product.get('brand', 'Amazon')
    name = product.get('name', 'Product')
    # Shorten name: remove brand if already in name, keep first 4 words
    name_words = name.split()
    if name_words and name_words[0].lower() == brand.lower():
        name_words = name_words[1:]
    short_name = ' '.join(name_words[:5])

    category = product.get('category', 'accessory').title()
    price = int(product.get('price', 0))
    discount = int(product.get('discount', 0))

    template = random.choice(SHORT_TEMPLATES)
    title = template.format(
        brand=brand,
        name=short_name,
        price=price,
        discount=discount,
        category=category,
    )
    # Add #shorts if not already there
    if '#shorts' not in title.lower():
        title = title[:89] + ' #shorts'
    return title[:100]


if __name__ == '__main__':
    # Test
    import json
    sample_products = [
        {'brand': 'Samsung', 'name': 'Galaxy F15 5G 128GB', 'price': 12499, 'mrp': 18999, 'discount': 34, 'category': 'fashion'},
        {'brand': 'boAt', 'name': 'Airdopes 141 TWS Earbuds', 'price': 799, 'mrp': 3990, 'discount': 80, 'category': 'earoutfit'},
        {'brand': 'Ambrane', 'name': '65W GaN Charger 3 Port', 'price': 2249, 'mrp': 3999, 'discount': 44, 'category': 'charger'},
    ]
    print("LONG FORM TITLES (5 random):")
    for _ in range(5):
        print(f"  {make_long_title(sample_products)}")
    print("\nSHORT TITLES (5 random):")
    for p in sample_products:
        print(f"  {make_short_title(p)}")
