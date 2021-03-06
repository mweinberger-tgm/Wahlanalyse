from datetime import datetime
from abc import ABCMeta
from sqlalchemy import create_engine
from sqlalchemy.ext.automap import automap_base
from sqlalchemy.orm import Session
from orderedset._orderedset import OrderedSet
import datetime
import time

"""
    Zustaendig fuer Lese- und Schreiboperationen in der Datenbank.

    Quelle:
    http://www.tutorialspoint.com/python/python_database_access.htm
"""
class DBHandler:

    def __init__(self, database, username, password):
        self.connector = MySQLDBConnector(database, username, password)
        self.wahltermin = str(datetime.datetime.fromtimestamp(time.time()).strftime('%Y-%m-%d'))

    """
        Speichert die angezeigte Tabelle in die Datenbank.
    """
    def write(self, rawdata):

        session = self.connector.get_session()
        session.execute("DELETE FROM Stimmabgabe")
        session.execute("DELETE FROM Sprengel")
        session.execute("DELETE FROM Wahl")

        Wahl = self.connector.get_class("Wahl")
        wahl = Wahl(termin=self.wahltermin, mandate=100)
        session.add(wahl)

        Sprengel = self.connector.get_class("Sprengel")
        Stimmabgabe = self.connector.get_class("Stimmabgabe")

        parteien = []
        for key in rawdata[0].keys():
            if key not in ["SPR", "BZ", "WBER", "ABG", "UNG", "T", "WV", "WK"]:
                parteien.append(key)

        for line in rawdata:
            sprengel = Sprengel(sprengelnr=int(line["SPR"]),
                                bezirknr=int(line["BZ"]),
                                termin=wahl.termin,
                                wahlberechtigte=int(line["WBER"]),
                                abgegebene=int(line["ABG"]),
                                ungueltige=int(line["UNG"]),
                                )
            session.add(sprengel)
            for partei in parteien:
                stimmabgabe = Stimmabgabe(sprengelnr=int(line["SPR"]),
                                          bezirknr=int(line["BZ"]),
                                          termin=wahl.termin,
                                          abkuerzung=partei,
                                          anzahl=int(line[partei])
                                          )
                session.add(stimmabgabe)

        session.commit()

    """
        Liest die in der Datenbank gespeicherten Rohdaten aus, und zeigt sie in der GUI an.
    """
    def load(self):

        session = self.connector.get_session()

        query = "SELECT Wahlkreis.wahlkreisnr, Bezirk.bezirknr, Sprengel.sprengelnr, Sprengel.wahlberechtigte, Sprengel.abgegebene, Sprengel.ungueltige, Stimmabgabe.abkuerzung, Stimmabgabe.anzahl FROM Wahlkreis INNER JOIN Bezirk ON Wahlkreis.wahlkreisnr = Bezirk.wahlkreisnr INNER JOIN Sprengel ON Bezirk.bezirknr = Sprengel.bezirknr AND Sprengel.termin = '" + self.wahltermin + "' INNER JOIN Stimmabgabe ON Stimmabgabe.termin = '" + self.wahltermin + "' AND Stimmabgabe.Bezirknr = Bezirk.bezirknr AND Stimmabgabe.sprengelnr = Sprengel.sprengelnr;"
        result = session.execute(query).fetchall()

        header = OrderedSet(["WK", "BZ", "SPR", "WBER", "ABG", "UNG"])
        rawdata = []
        line = {}
        erste_partei = None
        for i in range(0, len(result)):
            aktuelle_partei = result[i]["abkuerzung"]
            if erste_partei is None or aktuelle_partei == erste_partei:
                if line:
                    rawdata.append(line)
                line = {}
                erste_partei = aktuelle_partei
                line["WK"] = result[i]["wahlkreisnr"]
                line["BZ"] = result[i]["bezirknr"]
                line["SPR"] = result[i]["sprengelnr"]
                line["WBER"] = result[i]["wahlberechtigte"]
                line["ABG"] = result[i]["abgegebene"]
                line["UNG"] = result[i]["ungueltige"]
            line[aktuelle_partei] = result[i]["anzahl"]
            header.add(aktuelle_partei)

        return rawdata, list(header)

    """
        Erstellt eine Hochrechnung auf Basis der Rohdaten in der Datenbank.
    """
    def projection(self):

        termin = self.wahltermin
        zeitpunkt = datetime.datetime.now().time().strftime("%H:%M:%S")

        connection = self.connector.get_raw_connection()
        cursor = connection.cursor()
        cursor.callproc("erzeugeHochrechnung", [termin,zeitpunkt])
        cursor.close()
        connection.commit()

        session = self.connector.get_session()
        session.commit()
        query = "SELECT * FROM HRErgebnis WHERE termin = '" + termin + "' AND zeitpunkt = '" + zeitpunkt + "'"
        result = session.execute(query).fetchall()

        line = {}
        header = []
        rawdata = []
        for i in range(0, len(result)):
            line[result[i]["abkuerzung"]] = result[i]["prozent"]
            header.append(result[i]["abkuerzung"])
        rawdata.append(line)

        return rawdata, header

"""
    Die Verbindungsschnittstelle.
"""
class DBConnect(metaclass=ABCMeta):

    def __init__(self, connection_string):
        db = connection_string
        self.engine = create_engine(db)
        conn = self.engine.connect()
        Base = automap_base()
        Base.prepare(self.engine, reflect=True)
        self.session = Session(self.engine)
        self.classes = Base.classes

    def get_session(self):
        return self.session

    def get_raw_connection(self):
        return self.engine.raw_connection()

    def get_class(self, entity):
        return getattr(self.classes, entity)

"""
    Die Verbindungsschnittstelle zur MySQL-Datenbank.
"""
class MySQLDBConnector(DBConnect):
    def __init__(self, database, username, password):
        connection_string = "mysql+mysqldb://" + username + ":" + password + "@localhost/" + database + "?charset=utf8"
        super().__init__(connection_string)
