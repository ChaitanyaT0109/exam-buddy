# DBMS - Normalization (sample notes)

## Why normalize?
Normalization organises the tables of a relational database to reduce data redundancy (the same fact stored many
times) and to avoid update anomalies. A table that is not normalized can suffer three anomalies:
- **Insertion anomaly:** you cannot add a fact without adding an unrelated one (for example, you cannot add a new
  course until a student enrols in it).
- **Deletion anomaly:** deleting one fact deletes another by accident (deleting the last student of a course also
  deletes the course details).
- **Update anomaly:** the same fact is stored in many rows, so changing it in one row and not the others makes the
  data inconsistent.

## Keys and functional dependencies
- A **functional dependency** X -> Y means the value of X decides the value of Y. Example: RollNo -> Name.
- A **candidate key** is a minimal set of attributes that uniquely identifies every row. The one we choose is the
  **primary key**.
- A **prime attribute** is part of some candidate key; a **non-prime attribute** is not part of any candidate key.
- A **partial dependency** is when a non-prime attribute depends on only part of a composite key.
- A **transitive dependency** is when a non-prime attribute depends on another non-prime attribute
  (A -> B and B -> C, so A -> C through B).

## First Normal Form (1NF)
A table is in 1NF when every column holds **atomic (single) values** and there are no repeating groups. Example: a
"Phones" column holding "98480, 99490" breaks 1NF; store one phone number per row instead.

## Second Normal Form (2NF)
A table is in 2NF when it is in 1NF and has **no partial dependency**: every non-prime attribute depends on the
**whole** candidate key. Example: in Enrolment(RollNo, CourseID, StudentName, Grade) with key (RollNo, CourseID),
StudentName depends only on RollNo, so it is a partial dependency. Fix: move StudentName to a separate
Student(RollNo, StudentName) table.

## Third Normal Form (3NF)
A table is in 3NF when it is in 2NF and has **no transitive dependency**: non-prime attributes depend only on the
key, not on other non-prime attributes. Example: Student(RollNo, DeptID, DeptName) has RollNo -> DeptID and
DeptID -> DeptName, so DeptName depends on the key only through DeptID. Fix: move DeptName to a
Department(DeptID, DeptName) table.

## Boyce-Codd Normal Form (BCNF)
A table is in BCNF when, for **every** functional dependency X -> Y, X is a **superkey**. BCNF is stricter than
3NF: 3NF allows X -> Y when Y is a prime attribute, but BCNF does not. Every BCNF table is in 3NF, but not every
3NF table is in BCNF.

## Quick memory line
"The key, the whole key, and nothing but the key": 1NF = atomic values, 2NF = the whole key (no partial
dependency), 3NF = nothing but the key (no transitive dependency).

## Trade-off
Higher normal forms reduce redundancy and anomalies, but they split data into more tables, so queries need more
joins. Read-heavy systems sometimes **denormalize** on purpose for speed.
