import pandas as pd
from sklearn.metrics.pairwise import cosine_similarity

class CFiltering:
    def __init__(self, ratings_file, songs_file):
        self.ratings_file = ratings_file
        self.songs_file = songs_file
        self.refresh()
    def refresh(self):
        self.data = pd.read_csv(self.ratings_file)
        self.songs = pd.read_csv(self.songs_file)
        self.mean_rating = self.data['ratings'].mean()
        self.data['ratings'].fillna(self.mean_rating, inplace=True)
        self.user_item_matrix = self.data.pivot_table(index='userid', columns='songid', values='ratings').fillna(0)
        self.item_similarities = cosine_similarity(self.user_item_matrix.T)
    def get_recommendations(self, user_id, num_recommendations=10):
        self.user_ratings = self.user_item_matrix.loc[user_id]
        self.scores = self.item_similarities.dot(self.user_ratings)
    
        self.rated_song_indices = self.user_ratings[self.user_ratings > 0].index
        self.scores[self.rated_song_indices] = 0
        
        self.recommended_song_indices = self.scores.argsort()[-num_recommendations:][::-1]
        
        self.recommended_song_ids = self.user_item_matrix.columns[self.recommended_song_indices]
        self.recommended_songs = self.songs.loc[self.songs['songid'].isin(self.recommended_song_ids)]
        self.recommendations_list = []
        for i, row in self.recommended_songs.iterrows():
            self.recommendations_list.append({
                'songid': row['songid'],
                'name': row['name'],
                'artist': row['artist'],
                'year': row['year'],
                'genre': row['genre']
            })
        return self.recommendations_list[::-1]

cf = CFiltering('ratings.csv','cleansongsdata.csv')

if __name__ == "__main__":
    while True:
        user_id = int(input('\nuserID: '))
        if user_id == 'exit':
            break
        recommended_songs = cf.get_recommendations(user_id)
        for i in recommended_songs:
            print(i)
