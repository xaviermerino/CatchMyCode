import argparse
import csv
import multiprocessing as mp
import re
import xml.etree.ElementTree as ET
from os import chdir, getcwd, listdir, remove
from pathlib import Path
from shutil import copyfile, rmtree
from subprocess import run
from timeit import default_timer as timer
from zipfile import ZipFile, is_zipfile


def extract_all(submission_path):
    regexp = r"^([a-zA-Z]+)\_(\d+)\_\d+\_([a-zA-Z]+)([0-9]+)[(-?[a-f0-9]*]*\.zip$"
    given_files = [f for f in Path("given").glob("**/*") if f.is_file()]

    print("1) Running Pre-Checks")
    print("\t[✔][✔] --> Correct submission name and valid zip file")
    print("\t[✔][✘] --> Correct submission name but invalid zip file")
    print("\t[✘] -----> Incorrect submission name")
    print()
    with ZipFile(submission_path, 'r') as submission_archive:
        if (Path("submissions").exists()):
            rmtree("submissions")

        for index, student_submission_file in enumerate(submission_archive.namelist()):
            if student_submission_file.endswith('.zip'):
                matches = re.search(regexp, student_submission_file)

                if matches is None:
                    print("\t[✘]\tFile: ", student_submission_file)
                    continue

                student_name = matches.group(1)
                student_canvas_id = matches.group(2)
                student_tracks_id_name = matches.group(3).lower()
                student_tracks_id_year = str(matches.group(4))
                student_tracks_id = student_tracks_id_name + student_tracks_id_year
                submission_archive.filelist[index].filename = student_tracks_id + ".zip"
                submission_archive.extract(
                    submission_archive.filelist[index], "submissions")
                student_submission_archive_path = Path(
                    "submissions") / (student_tracks_id + ".zip")

                if is_zipfile(student_submission_archive_path):
                    print("\t[✔][✔]\tFile: ", student_submission_file)
                    with ZipFile(student_submission_archive_path, 'r') as student_submission:
                        student_submission.extractall(
                            Path("submissions") / student_tracks_id)

                    for f in given_files:
                        copyfile(f, Path("submissions") /
                                student_tracks_id / f.name)

                    remove(student_submission_archive_path)
                    submission_db[student_tracks_id] = [
                        student_name, student_canvas_id, Path("submissions") / student_tracks_id]
                else:
                    print("\t[✔][✘]\tFile: ", student_submission_file)

    print()

def grade(submission_path: Path):
    print("\tGrading: ", submission_path.name)
    chdir(submission_path)

    with open("compilation.txt", 'w') as compilation_results:
        run(["make"], stdout=compilation_results, stderr=compilation_results)

    obtained_grade = 0
    if Path("a.out").exists():
        xml_results_path = Path(getcwd()) / (submission_path.name + ".xml")
        command = ["./a.out", "-r", "xml", "-o", str(xml_results_path)]
        try:
            run(command, timeout=3, stdout=None, stderr=None)
        except:
            pass

        if Path(xml_results_path).exists():
            try:
                tree = ET.parse(xml_results_path)
                root = tree.getroot()
                overall = root.find('OverallResults')
                successes = int(overall.attrib['successes'])
                failures = int(overall.attrib['failures'])
                obtained_grade = float(
                    successes / (successes + failures)) * 100
            except:
                pass

    with open("grade.txt", 'w') as compilation_results:
        compilation_results.write(str(obtained_grade))

    return (submission_path.name, obtained_grade)


def grade_all():
    print("2) Grading Assigments")
    NAME, TRACKS_ID, PATH = range(3)
    submission_paths = [Path(getcwd()) / v[PATH]
                        for k, v in submission_db.items()]
    
    start = timer()
    
    pool = mp.Pool()
    grades = pool.map(grade, submission_paths)

    for student_tracks_id, obtained_grade in grades:
        submission_db[student_tracks_id].append(obtained_grade)
    
    end = timer()

    print()
    print("\tCompleted grading in {:.2f} seconds.".format(end - start))
    print()

def generate_gradebook():
    print("3) Generating Gradebook")
    with open(template_path, 'r') as csvFile:
        reader = csv.reader(csvFile)
        csvList = list(reader)

    NAME, TRACKS_ID, PATH, OBTAINED_GRADE = range(4)
    csv_names, csv_canvas_id, csv_student_tracks_id, csv_section, csv_assignment = zip(
        *csvList)
    csv_assignment = list(csv_assignment)

    for index, student_tracks_id in enumerate(csv_student_tracks_id):
        # Skip assignment name
        if index == 0:
            continue

        if student_tracks_id in submission_db.keys():
            if csv_assignment[index] == "":
                csv_assignment[index] = 0

            csv_assignment[index] = max(submission_db[student_tracks_id][OBTAINED_GRADE], int(csv_assignment[index]))
        else:
            csv_assignment[index] = 0

    csvList = zip(csv_names, csv_canvas_id, csv_student_tracks_id,
                  csv_section, csv_assignment)

    assignment_id = csv_assignment[0][csv_assignment[0].find("(")+1 : csv_assignment[0].find(")")]
    assignment_name = csv_assignment[0][0:csv_assignment[0].find("(")].strip()
    gradebook_name = "grades-" + assignment_id + ".csv"

    with open(gradebook_name, 'w') as csvFile:
        writer = csv.writer(csvFile)
        for row in csvList:
            writer.writerow(row)

    print("\tAssignment Name: '{}'".format(assignment_name))
    print("\tAssignment ID:\t", assignment_id)
    print("\tGradebook File:\t", gradebook_name)
    print()


parser = argparse.ArgumentParser(
    description="Grade students' homework based on unit testing.")
parser.add_argument('--submission',
                    type=str,
                    help='the path of the submission file')

parser.add_argument('--template',
                    type=str,
                    help='the path of the template file')

args = parser.parse_args()

if args.submission is None:
    submission_path = Path(getcwd()) / "submissions.zip"
else:
    if not (Path(args.submission).exists()):
        print("Submission does not exist!")
        exit(1)
    else:
        submission_path = Path(getcwd()) / args.submission

if args.template is None:
    template_path = Path(getcwd()) / "template.csv"
else:
    if not (Path(args.template).exists()):
        print("Template file does not exist!")
        exit(1)
    else:
        template_path = Path(getcwd()) / args.template

submission_db = dict()
print("Submission: ", submission_path)
print()

extract_all(submission_path)
grade_all()
generate_gradebook()