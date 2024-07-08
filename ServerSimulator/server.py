from flask import Flask,render_template
app = Flask(__name__)

@app.route('/')
def hello_world(name=None):
    return render_template('bookmarks.json',name = name)

if __name__ == '__main__':
    app.run(host='127.0.0.1',port=5000)