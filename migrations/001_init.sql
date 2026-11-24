CREATE TABLE concept (
  code      TEXT PRIMARY KEY,                 -- « es.ser-estar »
  langue    TEXT NOT NULL CHECK (langue IN ('en','es')),
  titre     TEXT NOT NULL,
  categorie TEXT NOT NULL,
  fiche     TEXT NOT NULL DEFAULT '',
  voisins   TEXT NOT NULL DEFAULT '[]'        -- JSON : codes
);

CREATE TABLE exercice (
  id          INTEGER PRIMARY KEY,
  concepts    TEXT NOT NULL,                  -- JSON : codes, le premier est le point principal
  type        TEXT NOT NULL CHECK (type IN ('trous','conjugaison','theme','transformation','choix','qcm','erreur')),
  consigne    TEXT NOT NULL,
  enonce      TEXT NOT NULL,
  reponses    TEXT NOT NULL,                  -- JSON : liste, ou liste par blanc (trous)
  distracteurs TEXT NOT NULL DEFAULT '[]',
  indice      TEXT NOT NULL DEFAULT '',
  explication TEXT NOT NULL DEFAULT '',
  difficulte  INTEGER NOT NULL DEFAULT 2 CHECK (difficulte BETWEEN 1 AND 3),
  source      TEXT NOT NULL CHECK (source IN ('manuel','import','ia','mcp','theme')),
  statut      TEXT NOT NULL CHECK (statut IN ('actif','a_valider','retire','archive')),
  empreinte   TEXT NOT NULL UNIQUE,
  cree_le     TEXT NOT NULL
);
CREATE INDEX exercice_statut ON exercice(statut);

CREATE TABLE tentative (
  id          INTEGER PRIMARY KEY,
  exercice    INTEGER NOT NULL REFERENCES exercice(id),
  date        TEXT NOT NULL,                  -- heure locale ISO
  mode        TEXT NOT NULL CHECK (mode IN ('jour','cible','rafale')),
  reponse     TEXT NOT NULL,                  -- JSON : une chaîne par blanc
  resultat    TEXT NOT NULL CHECK (resultat IN ('juste','aide','accent','faux')),
  code_erreur TEXT,
  duree       INTEGER NOT NULL DEFAULT 0,     -- secondes
  comptee     INTEGER NOT NULL DEFAULT 0      -- 1 : déjà répercutée sur etat_concept
);
CREATE INDEX tentative_exercice ON tentative(exercice, date);

CREATE TABLE etat_concept (
  concept    TEXT PRIMARY KEY REFERENCES concept(code),
  facilite   REAL NOT NULL DEFAULT 2.5,
  intervalle REAL NOT NULL DEFAULT 1,
  echeance   TEXT NOT NULL,                   -- AAAA-MM-JJ
  debut      TEXT NOT NULL                    -- jour de la première séance
);

CREATE TABLE reglage (cle TEXT PRIMARY KEY, valeur TEXT NOT NULL);
