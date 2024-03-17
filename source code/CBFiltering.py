import pandas as pd
from nltk.stem import PorterStemmer
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity

class CBFiltering:
    def __init__(self):
        self.df = None
        self.cosine_sim = None
        self.tfidf_vectorizer = TfidfVectorizer(stop_words='english')
        self.stemmer = PorterStemmer()

    def fit(self, data_path):
        self.df = pd.read_csv(data_path)
        self._stem()
        self._csm()

    def _stem(self):
        self.df['lyrics'] = self.df['lyrics'].apply(lambda x: ' '.join([self.stemmer.stem(word) for word in x.split()]))

    def _csm(self):
        tfidf_matrix = self.tfidf_vectorizer.fit_transform(self.df['lyrics'])
        self.cosine_sim = cosine_similarity(tfidf_matrix, tfidf_matrix)

    def get_recommendations(self, name):
        idx = self.df[self.df['name'] == name].index[0]
        sim_scores = list(enumerate(self.cosine_sim[idx]))
        sim_scores = sorted(sim_scores, key=lambda x: x[1], reverse=True)
        sim_scores = sim_scores[1:11]
        
        sindices = [i[0] for i in sim_scores]
        rsongs = []
        for index in sindices:
            row = self.df.drop(columns=['lyrics'])
            row_dict = row.iloc[index].to_dict()
            rsongs.append(row_dict)
    
        return rsongs

cbf = CBFiltering()
cbf.fit('cleansongsdata.csv')

if __name__ == "__main__":
    while True:
        name = input('Name: ')
        if name in "exit":
            break
        recommendations = cbf.get_recommendations(name)
        for i in recommendations:
            print(i)
