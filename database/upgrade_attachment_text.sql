-- À exécuter seulement si vous ne pouvez pas redémarrer Flask.
-- Le démarrage de l'application applique cette modification automatiquement.
ALTER TABLE messages
  MODIFY COLUMN attachment_text MEDIUMTEXT NULL;

-- Stocke les fragments de réponse et leur confiance déclarée.
ALTER TABLE messages
  ADD COLUMN confidence_segments JSON NULL;
