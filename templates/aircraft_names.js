// Aircraft names, keyed by ICAO type code. Hand-written: the lookups' own type text
// is inconsistent ("A320 251NSL"), so it isn't used. Codes not listed here are shown
// as they are. Filters, watchlists and drawings still use the code.
// templates/index.html includes this file into its main script.
const AIRCRAFT_NAMES = {
  // Airbus
  A306: 'Airbus A300-600', A30B: 'Airbus A300', A310: 'Airbus A310', A318: 'Airbus A318', A319: 'Airbus A319',
  A320: 'Airbus A320', A321: 'Airbus A321', A19N: 'Airbus A319neo', A20N: 'Airbus A320neo', A21N: 'Airbus A321neo',
  A332: 'Airbus A330-200', A333: 'Airbus A330-300', A337: 'Airbus BelugaXL', A338: 'Airbus A330-800neo', A339: 'Airbus A330-900neo',
  A342: 'Airbus A340-200', A343: 'Airbus A340-300', A345: 'Airbus A340-500', A346: 'Airbus A340-600',
  A359: 'Airbus A350-900', A35K: 'Airbus A350-1000', A388: 'Airbus A380-800', A3ST: 'Airbus Beluga', A400: 'Airbus A400M Atlas',
  BCS1: 'Airbus A220-100', BCS3: 'Airbus A220-300',
  // Boeing
  B712: 'Boeing 717-200', B721: 'Boeing 727-100', B722: 'Boeing 727-200',
  B732: 'Boeing 737-200', B733: 'Boeing 737-300', B734: 'Boeing 737-400', B735: 'Boeing 737-500', B736: 'Boeing 737-600',
  B737: 'Boeing 737-700', B738: 'Boeing 737-800', B739: 'Boeing 737-900',
  B37M: 'Boeing 737 MAX 7', B38M: 'Boeing 737 MAX 8', B39M: 'Boeing 737 MAX 9', B3XM: 'Boeing 737 MAX 10',
  B741: 'Boeing 747-100', B742: 'Boeing 747-200', B743: 'Boeing 747-300', B744: 'Boeing 747-400', B748: 'Boeing 747-8', B74S: 'Boeing 747SP',
  B752: 'Boeing 757-200', B753: 'Boeing 757-300', B762: 'Boeing 767-200', B763: 'Boeing 767-300', B764: 'Boeing 767-400',
  B772: 'Boeing 777-200', B773: 'Boeing 777-300', B77L: 'Boeing 777-200LR', B77W: 'Boeing 777-300ER', B778: 'Boeing 777-8', B779: 'Boeing 777-9',
  B788: 'Boeing 787-8', B789: 'Boeing 787-9', B78X: 'Boeing 787-10',
  MD11: 'McDonnell Douglas MD-11', MD82: 'McDonnell Douglas MD-82', MD83: 'McDonnell Douglas MD-83', MD87: 'McDonnell Douglas MD-87',
  MD88: 'McDonnell Douglas MD-88', MD90: 'McDonnell Douglas MD-90', DC10: 'McDonnell Douglas DC-10',
  // Other airliners and regional aircraft
  E170: 'Embraer E170', E75L: 'Embraer E175', E75S: 'Embraer E175', E190: 'Embraer E190', E195: 'Embraer E195',
  E290: 'Embraer E190-E2', E295: 'Embraer E195-E2', E135: 'Embraer ERJ 135', E145: 'Embraer ERJ 145', E45X: 'Embraer ERJ 145XR',
  CRJ1: 'Bombardier CRJ100', CRJ2: 'Bombardier CRJ200', CRJ7: 'Bombardier CRJ700', CRJ9: 'Bombardier CRJ900', CRJX: 'Bombardier CRJ1000',
  AT43: 'ATR 42-300', AT45: 'ATR 42-500', AT46: 'ATR 42-600', AT72: 'ATR 72-200', AT75: 'ATR 72-500', AT76: 'ATR 72-600',
  DH8A: 'De Havilland Dash 8-100', DH8B: 'De Havilland Dash 8-200', DH8C: 'De Havilland Dash 8-300', DH8D: 'De Havilland Dash 8-400',
  DHC6: 'De Havilland Twin Otter', B461: 'BAe 146-100', B462: 'BAe 146-200', B463: 'BAe 146-300', RJ85: 'Avro RJ85', RJ1H: 'Avro RJ100',
  F70: 'Fokker 70', F100: 'Fokker 100', F50: 'Fokker 50', SF34: 'Saab 340', SB20: 'Saab 2000', D328: 'Dornier 328', L410: 'Let L-410',
  A124: 'Antonov An-124', A148: 'Antonov An-148', A225: 'Antonov An-225', SU95: 'Sukhoi Superjet 100', C919: 'COMAC C919', AJ27: 'COMAC C909', IL76: 'Ilyushin Il-76', IL96: 'Ilyushin Il-96', B190: 'Beechcraft 1900',
  // Business jets
  C510: 'Cessna Citation Mustang', C525: 'Cessna CitationJet CJ1', C25A: 'Cessna Citation CJ2', C25B: 'Cessna Citation CJ3', C25C: 'Cessna Citation CJ4',
  C25M: 'Cessna Citation M2', C550: 'Cessna Citation II', C560: 'Cessna Citation V', C56X: 'Cessna Citation Excel', C680: 'Cessna Citation Sovereign',
  C68A: 'Cessna Citation Latitude', C700: 'Cessna Citation Longitude', C750: 'Cessna Citation X',
  CL30: 'Bombardier Challenger 300', CL35: 'Bombardier Challenger 350', CL60: 'Bombardier Challenger 600',
  CL85: 'Bombardier Challenger 850',
  GLEX: 'Bombardier Global Express', GL5T: 'Bombardier Global 5000', GL6T: 'Bombardier Global 6000', GL7T: 'Bombardier Global 7500',
  LJ35: 'Learjet 35', LJ40: 'Learjet 40', LJ45: 'Learjet 45', LJ60: 'Learjet 60', LJ75: 'Learjet 75',
  G280: 'Gulfstream G280', GLF4: 'Gulfstream G-IV', GLF5: 'Gulfstream G-V', GLF6: 'Gulfstream G650', GA5C: 'Gulfstream G500', GA6C: 'Gulfstream G600',
  FA50: 'Dassault Falcon 50', FA7X: 'Dassault Falcon 7X', FA8X: 'Dassault Falcon 8X', FA6X: 'Dassault Falcon 6X', F900: 'Dassault Falcon 900', F2TH: 'Dassault Falcon 2000',
  E35L: 'Embraer Legacy 600', E50P: 'Embraer Phenom 100', E55P: 'Embraer Phenom 300', E545: 'Embraer Legacy 450 / Praetor 500', E550: 'Embraer Legacy 500 / Praetor 600',
  H25B: 'Hawker 800', HDJT: 'HondaJet', PC24: 'Pilatus PC-24', PRM1: 'Beechcraft Premier I', BE40: 'Beechjet 400',
  // Light aircraft and turboprops
  C150: 'Cessna 150', C152: 'Cessna 152', C162: 'Cessna 162 Skycatcher', C172: 'Cessna 172 Skyhawk', C177: 'Cessna 177 Cardinal', C182: 'Cessna 182 Skylane',
  C206: 'Cessna 206', C208: 'Cessna 208 Caravan', C210: 'Cessna 210 Centurion', C310: 'Cessna 310', C414: 'Cessna 414',
  P28A: 'Piper PA-28 Cherokee', P28R: 'Piper PA-28R Arrow', P32R: 'Piper Saratoga', PA18: 'Piper Super Cub', PA24: 'Piper Comanche',
  PA31: 'Piper Navajo', PA34: 'Piper Seneca', PA44: 'Piper Seminole', PA46: 'Piper Malibu',
  SR20: 'Cirrus SR20', SR22: 'Cirrus SR22', DV20: 'Diamond DA20', DA40: 'Diamond DA40', DA42: 'Diamond DA42', DA62: 'Diamond DA62',
  BE20: 'Beechcraft King Air 200', B350: 'Beechcraft King Air 350', BE9L: 'Beechcraft King Air 90', BE35: 'Beechcraft Bonanza 35',
  BE36: 'Beechcraft Bonanza 36', BE58: 'Beechcraft Baron 58', M20P: 'Mooney M20', DR40: 'Robin DR400', Y18T: 'Yakovlev Yak-18T',
  S22T: 'Cirrus SR22T', RV7: "Van's RV-7", RV8: "Van's RV-8", RV12: "Van's RV-12", C42: 'Ikarus C42', EV97: 'Evektor EV-97', G115: 'Grob G 115',
  AC11: 'Rockwell Commander 112', BN2T: 'Britten-Norman Turbine Islander', J3: 'Piper J-3 Cub', EUPA: 'Europa', CLON: 'RotorSport Cavalon', GLID: 'Glider',
  TBM7: 'Daher TBM 700', TBM8: 'Daher TBM 850', TBM9: 'Daher TBM 900', PC6: 'Pilatus PC-6 Porter', PC12: 'Pilatus PC-12',
  // Helicopters
  R22: 'Robinson R22', R44: 'Robinson R44', R66: 'Robinson R66', EC20: 'Airbus H120', EC30: 'Airbus H130', EC35: 'Airbus H135', EC45: 'Airbus H145',
  EC55: 'Airbus H155', EC75: 'Airbus H175', EC25: 'Airbus H225', AS50: 'Airbus H125', AS55: 'Airbus AS355', AS65: 'Airbus AS365 Dauphin',
  A109: 'Leonardo AW109', A119: 'Leonardo AW119', A139: 'Leonardo AW139', A169: 'Leonardo AW169', A189: 'Leonardo AW189', EH10: 'Leonardo AW101',
  B06: 'Bell 206', B407: 'Bell 407', B412: 'Bell 412', B429: 'Bell 429', S76: 'Sikorsky S-76', S92: 'Sikorsky S-92', H60: 'Sikorsky Black Hawk', H47: 'Boeing Chinook',
  // Military
  C130: 'Lockheed C-130 Hercules', C17: 'Boeing C-17 Globemaster III', K35R: 'Boeing KC-135 Stratotanker', P8: 'Boeing P-8 Poseidon', EUFI: 'Eurofighter Typhoon', F35: 'Lockheed Martin F-35',
};
