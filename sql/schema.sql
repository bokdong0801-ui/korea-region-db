-- Korea Region DB schema v1
-- MySQL 8.x / utf8mb4

CREATE TABLE places (
  place_id VARCHAR(64) PRIMARY KEY,
  place_type VARCHAR(40) NOT NULL,
  name_ko VARCHAR(200) NOT NULL,
  full_name_ko VARCHAR(500) NOT NULL,
  official_code VARCHAR(32) NULL,
  parent_place_id VARCHAR(64) NULL,
  legal_status ENUM('CURRENT','ABOLISHED','PLANNED','UNKNOWN') NOT NULL DEFAULT 'CURRENT',
  valid_from DATE NULL,
  valid_to DATE NULL,
  source_id VARCHAR(80) NOT NULL,
  validity_source_id VARCHAR(80) NULL,
  source_snapshot_date DATE NULL,
  latitude DECIMAL(10,7) NULL,
  longitude DECIMAL(10,7) NULL,
  created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
  updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
  INDEX idx_places_type (place_type),
  INDEX idx_places_name (name_ko),
  INDEX idx_places_code (official_code),
  INDEX idx_places_parent (parent_place_id),
  CONSTRAINT fk_places_parent FOREIGN KEY (parent_place_id) REFERENCES places(place_id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;

CREATE TABLE place_aliases (
  alias_id BIGINT AUTO_INCREMENT PRIMARY KEY,
  place_id VARCHAR(64) NOT NULL,
  alias VARCHAR(200) NOT NULL,
  alias_type VARCHAR(40) NOT NULL DEFAULT 'COMMON',
  is_searchable BOOLEAN NOT NULL DEFAULT TRUE,
  source_id VARCHAR(80) NULL,
  UNIQUE KEY uq_alias (place_id, alias, alias_type),
  INDEX idx_alias_lookup (alias),
  CONSTRAINT fk_alias_place FOREIGN KEY (place_id) REFERENCES places(place_id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;

CREATE TABLE place_relations (
  relation_id BIGINT AUTO_INCREMENT PRIMARY KEY,
  from_place_id VARCHAR(64) NOT NULL,
  to_place_id VARCHAR(64) NOT NULL,
  relation_type VARCHAR(40) NOT NULL,
  confidence DECIMAL(5,4) NOT NULL DEFAULT 1.0000,
  source_id VARCHAR(80) NULL,
  valid_from DATE NULL,
  valid_to DATE NULL,
  UNIQUE KEY uq_relation (from_place_id, to_place_id, relation_type, valid_from, valid_to),
  INDEX idx_relation_from (from_place_id),
  INDEX idx_relation_to (to_place_id),
  CONSTRAINT fk_relation_from FOREIGN KEY (from_place_id) REFERENCES places(place_id),
  CONSTRAINT fk_relation_to FOREIGN KEY (to_place_id) REFERENCES places(place_id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;

CREATE TABLE place_history (
  history_id VARCHAR(32) PRIMARY KEY,
  place_id VARCHAR(64) NOT NULL,
  related_place_id VARCHAR(64) NULL,
  event_type ENUM('CREATED','RENAMED','ABOLISHED','MERGED','SPLIT','BOUNDARY_CHANGE','TYPE_CHANGE','UNKNOWN') NOT NULL,
  effective_date DATE NULL,
  note TEXT NULL,
  source_id VARCHAR(80) NOT NULL,
  INDEX idx_history_place (place_id),
  INDEX idx_history_related (related_place_id),
  INDEX idx_history_date (effective_date),
  CONSTRAINT fk_history_place FOREIGN KEY (place_id) REFERENCES places(place_id),
  CONSTRAINT fk_history_related FOREIGN KEY (related_place_id) REFERENCES places(place_id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;

CREATE TABLE source_snapshots (
  source_id VARCHAR(80) PRIMARY KEY,
  source_name VARCHAR(200) NOT NULL,
  authority VARCHAR(200) NOT NULL,
  source_url TEXT NOT NULL,
  snapshot_date DATE NULL,
  retrieved_at DATETIME NULL,
  source_grade CHAR(1) NOT NULL DEFAULT 'A',
  raw_filename VARCHAR(255) NULL,
  sha256 CHAR(64) NULL,
  note TEXT NULL
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;
