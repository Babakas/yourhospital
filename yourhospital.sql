CREATE DATABASE IF NOT EXISTS yourhospital;
USE yourhospital;

CREATE TABLE IF NOT EXISTS users (
    id INT AUTO_INCREMENT PRIMARY KEY,
    amka VARCHAR(11) NOT NULL UNIQUE,
    kwdikos VARCHAR(255) NOT NULL,
    role ENUM('admin', 'doctor', 'patient') NOT NULL
);

CREATE TABLE IF NOT EXISTS medicine (
    id INT AUTO_INCREMENT PRIMARY KEY,
    name VARCHAR(255) NOT NULL,
    posothta INT NOT NULL
);

CREATE TABLE IF NOT EXISTS beds (
    id INT AUTO_INCREMENT PRIMARY KEY,
    ktirio ENUM('A', 'B', 'C', 'D') NOT NULL,
    kathestws ENUM('eleuthero', 'kleismeno') NOT NULL
);

CREATE TABLE IF NOT EXISTS randevou (
    id INT AUTO_INCREMENT PRIMARY KEY,
    id_giatrou INT,
    id_asthenh INT,
    date DATE NOT NULL,
    time TIME NOT NULL,
    FOREIGN KEY (id_giatrou) REFERENCES users(id),
    FOREIGN KEY (id_asthenh) REFERENCES users(id)
);

INSERT INTO users (id , amka, kwdikos, role) VALUES
(1,'1111111111', 'adminpass', 'admin'),
(2,'2222222222', 'doctorpass', 'doctor'),
(3,'3333333333', 'patientpass', 'patient'),
(4,'04048045678', 'clinic2', 'doctor'),
(5,'05059056789', 'doctorx', 'doctor'),
(6,'11110011111', 'secure1', 'patient'),
(7,'22220022222', 'mypwd22', 'patient'),
(8,'33330033333', 'abc123', 'patient'),
(9,'44440044444', 'testme', 'patient'),
(10,'55550055555', 'passme', 'patient'),
(11,'66660066666', 'qwerty', 'patient'),
(12,'77770077777', 'health', 'patient'),
(13,'88880088888', 'simplep', 'patient'),
(14,'99990099999', 'pwd999', 'patient'),
(15,'12121012121', 'xyz121', 'patient'),
(16,'13131013131', 'alpha13', 'patient'),
(17,'14141014141', 'p@ssword', 'patient'),
(18,'15151015151', 'secure15', 'patient'),
(19,'16161016161', 'pass161', 'patient'),
(20,'17171017171', 'med161', 'patient'),
(21,'admin00001', 'adminpass', 'admin');

INSERT INTO medicine (id, name, posothta) VALUES
(1,'Παρακεταμόλη', 50),
(2,'Ιβουπροφαίνη', 30),
(3,'Ασπιρίνη', 20),
(4,'Αμοξικιλλίνη', 40),
(5,'Μετρονιδαζόλη', 25),
(6,'Δοξυκυκλίνη', 15),
(7,'Λοραταδίνη', 35),
(8,'Αζιθρομυκίνη', 18),
(9,'Διαζεπάμη', 12),
(10,'Ναλοξόνη', 10);
