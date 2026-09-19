# ====
# 02_product_classification.py
# Author: Sunday Emmanuel Azeez
# Seamark Global Innovations — Post-Launch Data Science Project (Project 2)
# Created: September 2026
# ====
#
# WHY I BUILT THIS:
# In Project 1, the Type column was empty for about 70% of the
# catalogue, so keyword matching on the Title carried almost the
# whole classification. This catalogue is different — Type is filled
# in for about 84% of products (245 of 275) — so this time Type is
# the primary source and keyword matching only fills the gaps,
# instead of the other way around. Trusting a column that's already
# mostly correct is more honest than re-deriving all of it from
# scratch a second time.
#
# THE OTHER NEW THING THIS CATALOGUE HAS:
# A "Shipping Destination" per product (UK / Nigeria / USA /
# Worldwide / Unspecified) that Project 1's catalogue never had.
# Sunday's new store is explicitly organised by category AND by
# country, so this script also produces a category-by-country
# breakdown, not just a category count.
# ====

import pandas as pd
import matplotlib.pyplot as plt
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.cluster import KMeans
from sklearn.metrics import adjusted_rand_score, silhouette_score

seamark_products = pd.read_csv('../cleaned_data/products_clean.csv')

print(f"Loaded {len(seamark_products)} products for classification")


# --
# STEP 1 — USE THE TYPE COLUMN WHERE IT EXISTS
# --
# Some raw Type values are close enough to each other that showing
# them separately would just fragment the same category (e.g. this
# store's export has 'Mobile Phones' and 'Smartphones' as separate
# values). Grouped the obvious ones together here rather than
# treating a vendor-typing quirk as a real category difference.
# --

TYPE_GROUPS = {
    'Smartphones': 'Smartphones',
    'Mobile Phones': 'Smartphones',
    'Watches': 'Watches',
    'Footwear': 'Footwear',
    'Fitness Equipment': 'Fitness Equipment',
    "Children's Clothing": "Children's Clothing",
    'Tops': 'Apparel',
    'Bottoms': 'Apparel',
    'Headphones': 'Audio',
    'Speakers': 'Audio',
    'Toys': 'Toys',
    'Pet Supplies': 'Pet Supplies',
    'Lighting': 'Home & Lighting',
    'Home Appliances': 'Home & Lighting',
    'Office Supplies': 'Office Supplies',
    'Bags & Wallets': 'Bags & Accessories',
    'Jewelry': 'Bags & Accessories',
    'Hats': 'Bags & Accessories',
    'Beauty & Personal Care': 'Beauty & Personal Care',
}


def classify_from_type(raw_type):
    return TYPE_GROUPS.get(raw_type)


# --
# STEP 2 — KEYWORD FALLBACK FOR THE ~16% WITH NO TYPE
# --
# Reused Project 1's keyword approach for the gap, updated for what
# this catalogue's 'Unknown'-Type products actually are (checked a
# sample of their titles before writing these rules, same as before).
# --

def classify_from_title(title):
    title = str(title).lower()

    if any(w in title for w in ['watch', 'smartwatch']):
        return 'Watches'
    elif any(w in title for w in ['phone', 'smartphone', 'redmi', 'xiaomi', 'iphone']):
        return 'Smartphones'
    elif any(w in title for w in ['shoe', 'sneaker', 'slipper', 'boot', 'sandal']):
        return 'Footwear'
    elif any(w in title for w in ['headphone', 'earphone', 'earbud', 'airpod', 'speaker']):
        return 'Audio'
    elif any(w in title for w in ['dress', 'top', 'blouse', 'skirt', 'trouser', 'jean', 'shirt', 't-shirt', 'tshirt']):
        return 'Apparel'
    elif any(w in title for w in ['toy', 'plush', 'doll', 'gift']):
        return 'Toys'
    elif any(w in title for w in ['fitness', 'gym', 'yoga', 'dumbbell', 'resistance band', 'exercise']):
        return 'Fitness Equipment'
    elif any(w in title for w in ['cat ', 'dog ', 'pet ', 'collar']):
        return 'Pet Supplies'
    elif any(w in title for w in ['light', 'lamp', 'led']):
        return 'Home & Lighting'
    elif any(w in title for w in ['bag', 'wallet', 'necklace', 'bracelet', 'ring', 'jewelry', 'jewellery']):
        return 'Bags & Accessories'
    else:
        return 'Other'


def classify_product(row):
    from_type = classify_from_type(row['Type'])
    if from_type is not None:
        return from_type
    return classify_from_title(row['Title'])


seamark_products['Auto_Category'] = seamark_products.apply(classify_product, axis=1)

print("\n=== AUTO-CLASSIFIED CATEGORIES ===")
print(seamark_products['Auto_Category'].value_counts())

other_count = (seamark_products['Auto_Category'] == 'Other').sum()
other_pct = round(other_count / len(seamark_products) * 100, 1)
print(f"\nUnclassified (Other): {other_count} products ({other_pct}%)")


# --
# STEP 3 — CATEGORY BY SHIPPING DESTINATION
# --
# This is the breakdown Project 1 could never produce — the old
# catalogue didn't have a country field on products at all. Built as
# a simple crosstab so it's easy to read straight off, and saved
# separately from the main products file since it's a summary table,
# not per-product data.
# --

category_by_country = pd.crosstab(
    seamark_products['Auto_Category'],
    seamark_products['Shipping Destination'],
)

print("\n=== CATEGORY BY SHIPPING DESTINATION ===")
print(category_by_country)


# --
# STEP 4 — UNSUPERVISED TEXT CLUSTERING (TF-IDF + K-MEANS)
# --
# Everything above is a RULE — Type-column lookup, then keyword
# matching. Rules are honest but they only find categories a human
# already thought to name. This step asks a different question: if a
# machine learning model looks purely at the words in each product's
# Title + Type + Tags, with no rules at all, does it independently
# rediscover roughly the same groupings — or does it find structure
# the rules missed?
#
# WHY THIS IS THE HONEST VERSION OF "USE CLUSTERING", NOT THE
# OVERCLAIMED ONE:
# Clustering by CUSTOMER BUYING BEHAVIOUR would need many customers
# each buying multiple products, so a "bought together" pattern has
# something to learn from. This store has 7 real orders. That is not
# enough rows to cluster behaviour from without the result being
# noise dressed up as insight. Clustering by PRODUCT TEXT, on the
# other hand, has 275 real rows to work with — enough for TF-IDF and
# K-Means to say something real. So this clusters what the data can
# actually support, and says so, rather than clustering "buying
# behaviour" on 7 orders and pretending the output means something.
# --

text_corpus = (
    seamark_products['Title'].fillna('') + ' ' +
    seamark_products['Type'].fillna('') + ' ' +
    seamark_products['Tags'].fillna('')
)

vectorizer = TfidfVectorizer(stop_words='english', max_features=500, min_df=2)
tfidf_matrix = vectorizer.fit_transform(text_corpus)

# Pick k by silhouette score over a small honest range rather than
# hard-coding a number — 2 is too coarse to be useful, 15 would start
# splitting single categories apart on this catalogue size.
best_k, best_score = None, -1
for k in range(4, 13):
    labels = KMeans(n_clusters=k, random_state=42, n_init=10).fit_predict(tfidf_matrix)
    score = silhouette_score(tfidf_matrix, labels)
    if score > best_score:
        best_k, best_score = k, score

kmeans = KMeans(n_clusters=best_k, random_state=42, n_init=10)
seamark_products['Text_Cluster'] = kmeans.fit_predict(tfidf_matrix)

print(f"\n=== TF-IDF + K-MEANS TEXT CLUSTERING ===")
print(f"Chosen k = {best_k} (silhouette score {round(best_score, 3)}, searched k=4..12)")

# Top terms per cluster — this is what makes a cluster label mean
# something to a human reading the output, not just a cluster number.
terms = vectorizer.get_feature_names_out()
cluster_top_terms = []
for cluster_id in range(best_k):
    center = kmeans.cluster_centers_[cluster_id]
    top_idx = center.argsort()[::-1][:8]
    top_terms = ', '.join(terms[i] for i in top_idx)
    cluster_size = int((seamark_products['Text_Cluster'] == cluster_id).sum())
    cluster_top_terms.append({'cluster': cluster_id, 'size': cluster_size, 'top_terms': top_terms})
    print(f"  Cluster {cluster_id} ({cluster_size} products): {top_terms}")

pd.DataFrame(cluster_top_terms).to_csv('../outputs/cluster_top_terms.csv', index=False)

# How much does the unsupervised clustering agree with the rule-based
# Auto_Category? Adjusted Rand Index is a real, standard metric for
# this (1.0 = identical grouping, 0.0 = no better than random) — used
# here as an honest cross-check, not to force the two to match.
ari = adjusted_rand_score(seamark_products['Auto_Category'], seamark_products['Text_Cluster'])
print(f"\nAgreement between rule-based categories and text clusters (Adjusted Rand Index): {round(ari, 3)}")
print("(1.0 = identical groupings, 0.0 = no better than random chance.")
print(" A moderate score is expected and fine — clustering groups by")
print(" WORDS USED, the rules group by INTENDED CATEGORY, and those")
print(" two don't always line up, e.g. a 'Smart Fitness Watch' pulls")
print(" toward both the Watches rule and a fitness-language cluster.)")

category_vs_cluster = pd.crosstab(seamark_products['Auto_Category'], seamark_products['Text_Cluster'])
category_vs_cluster.to_csv('../outputs/category_vs_cluster.csv')
print("Category-vs-cluster crosstab saved to outputs/category_vs_cluster.csv")


# --
# SAVE RESULTS
# --

seamark_products.to_csv('../cleaned_data/products_clean.csv', index=False)
category_by_country.to_csv('../outputs/category_by_country.csv')
print("\nUpdated products file saved to cleaned_data/products_clean.csv")
print("Category-by-country breakdown saved to outputs/category_by_country.csv")


# --
# VISUALISATION
# --

seamark_products['Auto_Category'].value_counts().plot(
    kind='bar',
    color='green',
    figsize=(10, 6),
)
plt.title('Seamark Product Categories — Auto Classification (Post-Launch Catalogue)')
plt.xlabel('Category')
plt.ylabel('Number of Products')
plt.tight_layout()
plt.savefig('../outputs/product_categories.png')

print("Chart saved to outputs/product_categories.png")
