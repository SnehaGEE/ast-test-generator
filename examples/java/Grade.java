// Run with: java -Dscore=85 Grade
public class Grade {
    public static void main(String[] args) {
        int score = Integer.parseInt(System.getProperty("score", "0"));

        if (score < 0 || score > 100) {
            System.out.println("Invalid score");
        } else if (score >= 90) {
            System.out.println("Grade A");
        } else if (score >= 75) {
            System.out.println("Grade B");
        } else if (score >= 40) {
            System.out.println("Grade C");
        } else {
            System.out.println("Fail");
        }
    }
}
