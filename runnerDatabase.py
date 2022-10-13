import copy, requests, json,math
from datetime import datetime, timedelta,date

remove_weekdays = False
weight_races = True
weight = .125
outlier_sensitivity = 15
remove_dates = []
#remove_dates = ["13-09-2022","27-09-2022"]
start_date = "01-09-2022" # September 1st (Saline)
#start_date = "19-08-2022" # August 19th (Lamp Lighter)

with open("athleteData.txt","r") as f:
    athlete_data = json.loads(f.read())

team_data = {}

def roundHundredths(value):
    return round(value*100) /100

def bubbleSort(data):
    n = len(data)
    new = copy.deepcopy(data)
    for i in range(n):
        for x in range(0,n-i-1):
            if(new[x] > new[x+1]):
                new[x],new[x+1] = new[x+1],new[x]
    return new

def average(data):
    if(len(data) == 0):
        return 0
    return roundHundredths(sum(data) / len(data))

def ratingToSeconds(rating):
    return 1560 - (3 * rating)

def secondsToTime(sec):
    time = str(timedelta(seconds=sec)).split(":")
    return time[1] + ":" + time[2][:4]

def timeToSeconds(time):
    mm,ss = time.split(":")[0],time.split(":")[1]
    return (int(mm) * 60) + float(ss)


def weightEquation(x):
    return int(roundHundredths(math.sqrt(x/15) + 1) * 100)

def calculateLinearRegression(xlist,ylist):
    if(len(xlist) < 3 or len(ylist) < 3):
        return {"Equation": "NED","Slope":0}

    weighted_xlist = []
    weighted_ylist = []
    weights = []
    for x,y in zip(xlist,ylist):
        weight = weightEquation(x)
        weights.append(weight/100)
        weighted_xlist.extend([x]*weight)
        weighted_ylist.extend([y]*weight)


    if not weight_races:
        weighted_xlist = xlist
        weighted_ylist = ylist

    avgX = average(weighted_xlist)
    avgY = average(weighted_ylist)

    diffX = []
    diffY = []

    SSxx = []

    SSxy = []

    for x in weighted_xlist:
        diffX.append(x-avgX)
    for y in weighted_ylist:
        diffY.append(y-avgY)

    for x in diffX:
        SSxx.append(x ** 2)
    SSxx = sum(SSxx)

    for x,y in zip(diffX,diffY):
        SSxy.append(x * y)
    SSxy = sum(SSxy)

    slope = SSxy/SSxx

    yint = (avgY - (slope * avgX))

    def regressionEquation(x):
        return slope * x + yint
    return {"Function": regressionEquation,"Equation": f"y = {slope}x + {yint}","Slope":slope,"YInt":yint,"X":xlist,"Y":ylist,"Weights":weights}

def generateToken(meetId):
    r = requests.get(f"https://www.athletic.net/api/v1/Meet/GetMeetData?meetId={meetId}&sport=xc")

    j = json.loads(r.text)

    return j["divisions"][0]["IDMeetDiv"],j["jwtMeet"]

def getTeamsRacing(meetId):
    div_id, token = generateToken(meetId)
    headers = {
        "content-type": "application/json",
        "anettokens": token
    }
    r = requests.get("https://www.athletic.net/api/v1/Meet/GetTeams",headers=headers)

    j = json.loads(r.text)
    teams = []
    for i in j:
        teams.append(i["SchoolName"])
    return teams

def getIndividualsRacing(meetId):
    div_id, token = generateToken(meetId)
    headers = {
        "content-type": "application/json",
        "anettokens": token
    }
    r = requests.get("https://www.athletic.net/api/v1/Meet/GetTeams",headers=headers)

    j = json.loads(r.text)



    return

def getMeetDate(meetId):
    r = requests.get(f"https://www.athletic.net/api/v1/Meet/GetMeetData?meetId={meetId}&sport=xc")
    j = json.loads(r.text)
    y,m,d = j["meet"]["MeetDate"].split("T")[0].split("-")
    return d + "-" + m + "-" + y

def calculatePrediction(name,day):
    return roundHundredths((athlete_data[name]["RatingData"]["RegressionData"]["Function"](day) * weight * 2 + athlete_data[name]["RatingData"]["BestRating"] * (1 - weight) * 2)/2)

def predictMeet(meetId,gender = "M",getTeams = True,number_of_places = 0,excludeTeams = [],excludeRunners = [],manualRating = []):
    if getTeams:
        teams = getTeamsRacing(meetId)
    else:
        teams = getIndividualsRacing(meetId)
    meet_date = getMeetDate(meetId)
    days = daysAfterSeasonStart(meet_date)

    all_runners = []
    team_scores = {}
    for team in teams:
        if team in excludeTeams:
            continue
        try:
            team_data[team]
        except:
            continue
        team_scores[team] = {"Score":0,"Runners":0,"TopSeven":[]}
        for runner in team_data[team]:
            name = list(runner.keys())[0]
            if name in excludeRunners:
                continue
            if runner[name]["Gender"] != gender:
                continue
            portfolio = {
                    "Name":name,
                    "PlaceOnTeam":0,
                    "Grade":runner[name]["Grade"],
                    "School":team,
                    "RegressionEquation":runner[name]["RatingData"]["RegressionData"]["Equation"]
            }

            for i in manualRating:
                try:
                    manual_rating = i[name]
                    portfolio["PredictedRating"] = manual_rating
                except:
                    continue

            try:
                portfolio["PredictedRating"]
            except:   
                try:
                    if runner[name]["RatingData"]["RegressionData"]["Equation"] != "NED":
                        portfolio["PredictedRating"] = calculatePrediction(name,days)
                    elif len(runner[name]["RatingData"]["Ratings"]) == 1 or len(runner[name]["RatingData"]["Ratings"]) == 2:
                        portfolio["PredictedRating"] = runner[name]["RatingData"]["BestRating"]
                    else:
                        continue
                except Exception as e:
                    print(e)
                    continue    
            all_runners.append(portfolio)

    n = len(all_runners)
    for x in range(n):
        for y in range(0,n-x-1):
            if(all_runners[y]["PredictedRating"] > all_runners[y+1]["PredictedRating"]):
                all_runners[y],all_runners[y+1] = all_runners[y+1],all_runners[y]

    all_runners.reverse()
    for runner in all_runners:
        if len(team_scores[runner["School"]]["TopSeven"]) < 7:
            team_scores[runner["School"]]["TopSeven"].append(runner)
            runner["PlaceOnTeam"] = len(team_scores[runner["School"]]["TopSeven"])

    for i in range(len(all_runners)):
        for runner in all_runners:
            if runner["PlaceOnTeam"] == 0:
                all_runners.remove(runner)

    table = []
    for place,runner in enumerate(all_runners):
        if(team_scores[runner["School"]]["Runners"] < 5):
            team_scores[runner["School"]]["Score"] += place + 1
            team_scores[runner["School"]]["Runners"] += 1
        table.append([place +1,runner["Name"],runner["Grade"],runner["School"],runner["PlaceOnTeam"],runner["PredictedRating"],secondsToTime(ratingToSeconds(runner["PredictedRating"])),runner["RegressionEquation"]])

    column_lengths = []
    for i in range(len(table[0])):
        column_lengths.append(0)

    for table_row in table:
        for column,table_data in enumerate(table_row):
            if column_lengths[column] < len(str(table_data)):
                column_lengths[column] = len(str(table_data)) + 3

    table_string = ""
    for table_row in table:
        for column,table_data in enumerate(table_row):
            table_string += str(table_data) + (" " * (column_lengths[column] - len(str(table_data))))
        table_string += "\n"
    print(table_string)

    
    
    n = len(team_scores)
    team_keys = list(team_scores.keys())
    for x in range(n):
        for y in range(0,n-x-1):
            if(team_scores[team_keys[y]]["Score"] > team_scores[team_keys[y+1]]["Score"]):
                team_keys[y], team_keys[y+1] = team_keys[y+1],team_keys[y]
    
    place = 1
    for team in team_keys:
        if(team_scores[team]["Runners"] < 5):
            continue
        print(place,team,team_scores[team]["Score"])
        place+=1

def daysAfterSeasonStart(input):
    meet_date = datetime.strptime(input, "%d-%m-%Y")
    season_start = datetime.strptime(start_date, "%d-%m-%Y")
    difference = meet_date - season_start
    return difference.days

def median(data):
    new = copy.deepcopy(data)
    new = bubbleSort(new)
    n = len(new)
    if (n % 2 == 0):
        return (new[int(n/2)] + new[int((n/2) - 1)])/2
    else:
        return new[int((n - 1)/2)]

def outlierCalculator(data):
    avg = average(data)
    outliers = []
    for i in data:
        if avg - outlier_sensitivity > i:
            outliers.append(i)

    return {"Outliers":outliers}


for name in athlete_data.keys():
    team = athlete_data[name]["School"]

    meets = []
    for meet in athlete_data[name]["RatingData"]:
        if datetime.strptime(meet["Date"],"%d-%m-%Y") >= datetime.strptime(start_date,"%d-%m-%Y"):
            if (remove_weekdays and datetime.strptime(meet["Date"],"%d-%m-%Y").weekday() >= 4) or not remove_weekdays:
                if not meet["Date"] in remove_dates:
                    meets.append(meet)

    ratings = []
    times = []
    days = []
    for data in meets:
        times.append(timeToSeconds(data["Time"]))
        ratings.append(float(data["Rating"]))
        days.append(daysAfterSeasonStart(data["Date"]))


    outlier_data = outlierCalculator(ratings)
    x = []
    y = []
    best_rating = 0
    for rating, day in zip(ratings,days):
        if rating > best_rating:
            best_rating = rating
        if not rating in outlier_data["Outliers"]:
            x.append(day)
            y.append(rating)

    regression_data = calculateLinearRegression(x,y)
    
    athlete_data[name]["RatingData"] = {"OutlierData":outlier_data,"RegressionData":regression_data,"BestRating":best_rating,"AverageRating":average(ratings),"AverageTime":average(times),"Ratings":bubbleSort(ratings),"Times":bubbleSort(times),"Meets":meets}
    try:
        team_data[team].append({name:athlete_data[name]})
    except:
        team_data[team] = [{name:athlete_data[name]}]


#predictMeet(207940,gender="M",excludeTeams=["Yale","Croswell-Lexington"],excludeRunners=["Luke VanderHeuvel","Gregory Vogt"])
# region


predictMeet(205620,gender="M",excludeRunners=["Gregory Vogt","Ethan Muraszewski"])
#print(athlete_data["Remi Flanz"]["RatingData"])
# counties


#print(athlete_data["Tyler Donovan"]["RatingData"]["RegressionData"])


