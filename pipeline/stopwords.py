"""Malay and English function words, plus words the descriptions overuse.

Without this the TF-IDF baseline scores entries as similar because they share
"yang dan dengan di" rather than because they mean anything alike.
"""

MALAY = """
adalah akan antara apa apabila atas atau bagi bahawa banyak baru berupa besar
bagaimana bawah beberapa begitu bentuk berada berikut bersama bila bukan
buat dalam dan dapat dari daripada dengan di dia dua hanya hingga ia iaitu
ialah ini itu jadi jika juga kali kami kamu ke kecuali kemudian kepada kerana
ketika kini lagi lain lalu lebih maka malah mana masih melalui memang mempunyai
mereka mesti mungkin nya oleh pada paling para pula pun sahaja saja sama sambil
sangat satu saya sebagai sebelum sebuah secara sedang segala sehingga sejak
selain selalunya semua semasa sementara seorang seperti serta sesuatu setelah
siapa sini situ sudah supaya tanpa telah tentang terhadap terlalu tetapi tiada
tidak turut untuk walaupun yang
""".split()

ENGLISH = """
a about after all also an and are as at be been being but by can come could
during each for from had has have her here his how in including into is it its
like made make many may more most much no not now of on once one only or other
out over own same she she's so some such than that the their them then there
these they this those through to too under until up upon use used using very
was were what when where which while who whose why will with within without
would you your
""".split()

# Vocabulary the descriptions themselves lean on; high document frequency here
# carries no signal about what an entry actually is.
BOILERPLATE = """
also called known name named nama dikenali digelar dipanggil
malaysia malaysian negara country national kebangsaan
served serve dihidang dimakan eaten
traditional tradisional traditionally
community masyarakat golongan penduduk
festival perayaan sambutan disambut celebrated
""".split()

STOPWORDS = sorted(set(MALAY) | set(ENGLISH) | set(BOILERPLATE))
