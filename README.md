# Dzeck

Dzeck adalah sebuah headless browser engine berkinerja tinggi yang ditulis sepenuhnya dalam bahasa pemrograman Rust. Proyek ini dirancang untuk menyediakan solusi otomatisasi web, pengujian, dan web scraping yang cepat, aman, dan efisien memori tanpa memerlukan antarmuka grafis. Berbeda dengan pendekatan tradisional yang membungkus browser existing, Dzeck membangun rendering pipeline dan eksekusi JavaScript dari dasar dengan memanfaatkan sistem tipe Rust dan manajemen memori yang aman untuk mencapai latensi rendah dan konkurensi tingkat tinggi.

## Fitur Utama

Engine ini menawarkan dukungan penuh terhadap standar web modern termasuk HTML5, CSS3, dan ES2024+ dengan fokus pada kepatuhan spesifikasi yang ketat. Dzeck dilengkapi dengan runtime JavaScript bawaan yang dioptimalkan untuk operasi headless, mendukung DOM manipulation, network interception, dan evaluasi skrip asinkron secara native. Keamanan menjadi prioritas utama dengan sandboxing otomatis untuk setiap konteks browsing, isolasi proses, dan mitigasi kerentanan memori berkat arsitektur Rust yang bebas dari data race dan buffer overflow. Selain itu, Dzeck menyediakan API ergonomis baik untuk pengguna Rust maupun binding untuk bahasa lain seperti Python dan Node.js melalui FFI.

## Instalasi dan Persyaratan Sistem

Untuk menggunakan Dzeck sebagai dependensi dalam proyek Rust Anda, pastikan Anda telah menginstal Rust toolchain versi 1.75 atau lebih baru melalui rustup. Tambahkan crate dzeck ke dalam file Cargo.toml Anda dengan menjalankan perintah `cargo add dzeck` di direktori proyek. Untuk instalasi dari source code, kloning repositori ini dan jalankan `cargo build --release` untuk menghasilkan binary yang teroptimasi. Dzeck mendukung platform Linux (x86_64, aarch64), macOS (Intel dan Apple Silicon), serta Windows (MSVC). Pada lingkungan Linux server tanpa display, pastikan library sistem seperti libfontconfig dan libfreetype telah terinstal karena engine ini melakukan rasterisasi font secara independen.

## Contoh Penggunaan Dasar

Berikut adalah contoh sederhana bagaimana menginisialisasi sesi browser headless dan mengekstrak konten halaman web. Buat file baru bernama main.rs dan salin kode berikut:

```rust
use dzeck::prelude::*;

#[tokio::main]
async fn main() -> Result<(), Box<dyn std::error::Error>> {
    // Inisialisasi engine dengan konfigurasi default
    let browser = DzeckBrowser::launch(BrowserConfig::headless()).await?;
    
    // Buka halaman target
    let page = browser.new_page().await?;
    page.goto("https://example.com").await?;
    
    // Tunggu selector tertentu muncul sebelum ekstraksi
    page.wait_for_selector("h1", WaitOptions::default()).await?;
    
    // Ambil teks dari elemen
    let title = page.text_content("h1").await?;
    println!("Judul Halaman: {}", title.unwrap_or_default());
    
    // Tangkap screenshot dalam format PNG
    let screenshot = page.screenshot(ScreenshotFormat::Png).await?;
    tokio::fs::write("output.png", screenshot).await?;
    
    // Tutup sesi browser secara graceful
    browser.close().await?;
    Ok(())
}
```

Kode di atas mendemonstrasikan alur kerja asinkron menggunakan Tokio runtime. Dzeck menangani manajemen siklus hidup halaman, pembersihan sumber daya, dan error handling secara eksplisit melalui tipe Result Rust sehingga developer dapat menulis kode otomasi yang robust dan mudah di-debug.

## Arsitektur dan Desain Internal

Dzeck mengadopsi arsitektur modular yang memisahkan parsing, styling, layout, dan painting ke dalam crate-crate terpisah. Core engine menggunakan event loop berbasis async/await untuk menangani I/O jaringan dan timer tanpa blocking thread utama. Rendering pipeline menerapkan incremental layout computation yang hanya memperbarui subtree yang berubah, mengurangi overhead CPU secara signifikan pada halaman dinamis. Integrasi dengan GPU bersifat opsional; secara default Dzeck menggunakan software rasterizer berbasis SIMD untuk konsistensi output lintas platform, namun dapat dikonfigurasi untuk menggunakan Vulkan atau Metal jika akselerasi hardware diperlukan untuk rendering canvas berat atau WebGL.

## Kontribusi dan Pengembangan

Kami menyambut kontribusi dari komunitas open source untuk menjadikan Dzeck lebih baik. Sebelum mengirimkan Pull Request, pastikan Anda telah menjalankan test suite lengkap dengan `cargo test --all-features` dan memformat kode dengan `cargo fmt`. Kami merekomendasikan penggunaan clippy untuk linting statis guna menjaga kualitas kode sesuai idiom Rust. Dokumentasi API dihasilkan secara otomatis melalui cargo doc dan tersedia di docs.rs/dzeck. Untuk diskusi fitur, pelaporan bug, atau pertanyaan teknis, silakan buka issue di tracker GitHub kami dengan label yang sesuai. Lisensi proyek ini adalah MIT/Apache-2.0 dual license, memberikan fleksibilitas maksimal untuk penggunaan komersial maupun akademis.
