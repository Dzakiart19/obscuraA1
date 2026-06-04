import requests
from bs4 import BeautifulSoup
import pandas as pd
from collections import Counter

def scrape_quotes():
    quotes_data = []
    page = 1
    
    while True:
        url = f'https://quotes.toscrape.com/page/{page}/'
        response = requests.get(url)
        
        if response.status_code != 200:
            break
            
        soup = BeautifulSoup(response.text, 'html.parser')
        quote_divs = soup.find_all('div', class_='quote')
        
        if not quote_divs:
            break
            
        for quote_div in quote_divs:
            text = quote_div.find('span', class_='text').get_text()
            author = quote_div.find('small', class_='author').get_text()
            tags = [tag.get_text() for tag in quote_div.find_all('a', class_='tag')]
            
            quotes_data.append({
                'text': text,
                'author': author,
                'tags': tags
            })
        
        next_button = soup.find('li', class_='next')
        if not next_button:
            break
            
        page += 1
    
    return quotes_data

def analyze_quotes(quotes_data):
    df = pd.DataFrame(quotes_data)
    
    # Analisis dasar
    total_quotes = len(df)
    unique_authors = df['author'].nunique()
    
    # Penulis dengan kutipan terbanyak
    top_authors = df['author'].value_counts().head(5)
    
    # Tag paling populer
    all_tags = []
    for tags in df['tags']:
        all_tags.extend(tags)
    tag_counter = Counter(all_tags)
    top_tags = tag_counter.most_common(10)
    
    # Rata-rata panjang kutipan
    df['quote_length'] = df['text'].apply(len)
    avg_length = df['quote_length'].mean()
    longest_quote_idx = df['quote_length'].idxmax()
    longest_quote = df.loc[longest_quote_idx]
    
    return {
        'total_quotes': total_quotes,
        'unique_authors': unique_authors,
        'top_authors': top_authors,
        'top_tags': top_tags,
        'avg_quote_length': avg_length,
        'longest_quote': longest_quote,
        'dataframe': df
    }

if __name__ == '__main__':
    print("Memulai scraping data dari quotes.toscrape.com...")
    quotes = scrape_quotes()
    print(f"Berhasil mengambil {len(quotes)} kutipan.\n")
    
    print("Melakukan analisis data...")
    analysis = analyze_quotes(quotes)
    
    print("=" * 60)
    print("HASIL ANALISIS DATA QUOTES")
    print("=" * 60)
    print(f"Total Kutipan: {analysis['total_quotes']}")
    print(f"Jumlah Penulis Unik: {analysis['unique_authors']}")
    print(f"Rata-rata Panjang Kutipan: {analysis['avg_quote_length']:.2f} karakter")
    
    print("\nTop 5 Penulis dengan Kutipan Terbanyak:")
    for author, count in analysis['top_authors'].items():
        print(f"  - {author}: {count} kutipan")
    
    print("\nTop 10 Tag Paling Populer:")
    for tag, count in analysis['top_tags']:
        print(f"  - {tag}: {count} kali muncul")
    
    print("\nKutipan Terpanjang:")
    print(f"  Penulis: {analysis['longest_quote']['author']}")
    print(f"  Teks: {analysis['longest_quote']['text'][:200]}...")
    print(f"  Panjang: {analysis['longest_quote']['quote_length']} karakter")
    
    # Simpan hasil ke CSV
    analysis['dataframe'].to_csv('quotes_analysis.csv', index=False)
    print("\nData lengkap telah disimpan ke 'quotes_analysis.csv'")
