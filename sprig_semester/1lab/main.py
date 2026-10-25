def _download_nltk_data():
    import nltk
    resources = [
        ("tokenizers/punkt_tab", "punkt_tab"),
        ("corpora/wordnet", "wordnet"),
        ("taggers/averaged_perceptron_tagger_eng", "averaged_perceptron_tagger_eng"),
    ]
    for path, pkg in resources:
        try:
            nltk.data.find(path)
        except LookupError:
            print(f"Downloading NLTK resource: {pkg}")
            nltk.download(pkg, quiet=True)


if __name__ == "__main__":
    _download_nltk_data()

    from gui.main_window import MainWindow

    app = MainWindow()
    app.mainloop()
