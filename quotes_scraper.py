import requests
from bs4 import BeautifulSoup
import pandas as pd
from collections import Counter

def scrape_quotes():
    """Mengambil semua quotes dari quotes.toscrape.com"""
    base_url = 'https://quotes.toscrape.com'
    all_quotes = []
    page = 1
    
    while True:
        url = f'{base_url}/page/{page}/'
        response = requests.get(url)
        
        if response.status_code != 200:
            break
            
        soup = BeautifulSoup(response.text, 'html.parser')
        quotes_div = soup.find_all('div', class_='quote')
        
        if not quotes_div:
            break
            
        for quote_div in quotes_div:
            text = quote_div.find('span', class_='text').get_text()
            author = quote_div.find('small', class_='author').get_text()
            tags = [tag.get_text() for tag in quote_div.find_all('a', class_='tag')]
            
            all_quotes.append({
                'text': text,
                'author': author,
                'tags': tags
            })
        
        # Cek apakah ada halaman berikutnya
        next_button = soup.find('li', class_='next')
        if not next_button:
            break
            
        page += 1
    
    return all_quotes

def analyze_quotes(quotes):
    """Melakukan analisis pada data quotes"""
    df = pd.DataFrame(quotes)
    
    # Analisis dasar
    total_quotes = len(df)
    unique_authors = df['author'].nunique()
    
    # Penulis dengan quote terbanyak
    top_authors = df['author'].value_counts().head(5)
    
    # Tag paling populer
    all_tags = []
    for tags in df['tags']:
        all_tags.extend(tags)
    tag_counter = Counter(all_tags)
    top_tags = tag_counter.most_common(10)
    
    # Rata-rata panjang quote
    df['quote_length'] = df['text'].apply(len)
    avg_length = df['quote_length'].mean()
    longest_quote_idx = df['quote_length'].idxmax()
    shortest_quote_idx = df['quote_length'].idxmin()
    
    analysis_results = {
        'total_quotes': total_quotes,
        'unique_authors': unique_authors,
        'top_authors': top_authors,
        'top_tags': top_tags,
        'avg_quote_length': round(avg_length, 2),
        'longest_quote': df.loc[longest_quote_idx],
        'shortest_quote': df.loc[shortest_quote_idx]
    }
    
    return df, analysis_results

def display_results(df, results):
    """Menampilkan hasil analisis"""
    print("=" * 60)
    print("HASIL ANALISIS QUOTES")
    print("=" * 60)
    
    print(f"\nTotal Quotes: {results['total_quotes']}")
    print(f"Jumlah Penulis Unik: {results['unique_authors']}")
    print(f"Rata-rata Panjang Quote: {results['avg_quote_length']} karakter")
    
    print("\n--- Top 5 Penulis dengan Quote Terbanyak ---")
    for author, count in results['top_authors'].items():
        print(f"{author}: {count} quotes")
    
    print("\n--- Top 10 Tag Paling Populer ---")
    for tag, count in results['top_tags']:
        print(f"{tag}: {count} kali")
    
    print("\n--- Quote Terpanjang ---")
    print(f"Penulis: {results['longest_quote']['author']}")
    print(f"Quote: {results['longest_quote']['text']}")
    print(f"Panjang: {results['longest_quote']['quote_length']} karakter")
    
    print("\n--- Quote Terpendek ---")
    print(f"Penulis: {results['shortest_quote']['author']}")
    print(f"Quote: {results['shortest_quote']['text']}")
    print(f"Panjang: {results['shortest_quote']['quote_length']} karakter")
    
    print("\n--- Contoh 5 Quote Pertama ---")
    for idx, row in df.head().iterrows():
        print(f"\n[{row['author']}]")
        print(f"{row['text']}")
        print(f"Tags: {', '.join(row['tags'])}")
    
    print("\n" + "=" * 60)

if __name__ == '__main__':
    print("Memulai scraping quotes...")
    quotes = scrape_quotes()
    print(f"Berhasil mengambil {len(quotes)} quotes.")
    
    print("\nMelakukan analisis...")
    df, results = analyze_quotes(quotes)
    
    print("\nMenampilkan hasil...\n")
    display_results(df, results)
    
    # Simpan ke CSV
    df.to_csv('quotes_data.csv', index=False)
    print("\nData telah disimpan ke 'quotes_data.csv'")
